"""UbiFleet — Budget Views"""

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import RoleBasedPermission
from apps.core.agences import (
    AgenceMixin, agence_effective, agence_pour_creation, controler_agence, filtrer_par_agence,
)
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters import rest_framework as df
from django.db.models import Sum, Count
from django.utils import timezone

from .models import BudgetAnnuel, DepenseVehicule


class BudgetAnnuelSerializer:
    pass  # imported from serializers.py


class DepenseFilter(FilterSet):
    agence = df.UUIDFilter()
    vehicule = df.UUIDFilter()
    categorie = df.MultipleChoiceFilter(choices=DepenseVehicule.Categorie.choices)
    date_min = df.DateFilter(field_name='date_depense', lookup_expr='gte')
    date_max = df.DateFilter(field_name='date_depense', lookup_expr='lte')
    mois = df.NumberFilter(field_name='date_depense__month')
    annee = df.NumberFilter(field_name='date_depense__year')

    class Meta:
        model = DepenseVehicule
        fields = ['agence', 'vehicule', 'categorie']


from .serializers import BudgetAnnuelSerializer, DepenseSerializer


class BudgetViewSet(AgenceMixin, viewsets.ModelViewSet):
    """
    CRUD budgets annuels.
    GET /budgets/tableau_de_bord/ — synthèse budgétaire multi-agences
    """
    serializer_class = BudgetAnnuelSerializer
    module   = 'budget'
    role_map = {
            'list': 'comptable',
            'retrieve': 'comptable',
            'create': 'responsable_flotte',
            'update': 'responsable_flotte',
            'partial_update': 'responsable_flotte',
            'destroy': 'super_admin',
            'tableau_de_bord': 'comptable',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['agence', 'annee']

    agence_a_la_creation = True

    def get_queryset(self):
        return self.filtrer_agence(BudgetAnnuel.objects.select_related('agence'))

    @action(detail=False, methods=['get'])
    def tableau_de_bord(self, request):
        annee = request.query_params.get('annee', timezone.now().year)
        agence_id = agence_effective(request.user, request.query_params.get('agence'))

        qs = DepenseVehicule.objects.filter(date_depense__year=annee)
        if agence_id:
            qs = qs.filter(agence_id=agence_id)

        global_agg = qs.aggregate(total=Sum('montant'))
        par_categorie = list(
            qs.values('categorie')
              .annotate(total=Sum('montant'), nb=Count('id'))
              .order_by('-total')
        )
        par_mois = list(
            qs.values('date_depense__month')
              .annotate(total=Sum('montant'))
              .order_by('date_depense__month')
        )
        par_agence = list(
            qs.values('agence__nom', 'agence__code')
              .annotate(total=Sum('montant'))
              .order_by('-total')
        )
        par_vehicule = list(
            qs.values('vehicule__immatriculation', 'vehicule__marque', 'vehicule__modele')
              .annotate(total=Sum('montant'))
              .order_by('-total')[:10]
        )
        budgets = BudgetAnnuel.objects.filter(annee=annee)
        if agence_id:
            budgets = budgets.filter(agence_id=agence_id)
        budget_total = budgets.aggregate(
            carburant=Sum('budget_carburant'),
            entretien=Sum('budget_entretien'),
            reparations=Sum('budget_reparations'),
            assurances=Sum('budget_assurances'),
            divers=Sum('budget_divers'),
        )
        return Response({
            'annee': annee,
            'total_realise': global_agg['total'] or 0,
            'par_categorie': par_categorie,
            'par_mois': par_mois,
            'par_agence': par_agence,
            'top_vehicules': par_vehicule,
            'budgets_prevus': budget_total,
        })


class DepenseViewSet(viewsets.ModelViewSet):
    serializer_class = DepenseSerializer

    module   = 'budget'
    role_map = {
        'list': 'comptable',
        'retrieve': 'comptable',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }

    role_map = {
            'list': 'comptable',
            'retrieve': 'comptable',
            'create': 'responsable_flotte',
            'update': 'responsable_flotte',
            'partial_update': 'responsable_flotte',
            'destroy': 'super_admin',
            'tableau_de_bord': 'comptable',
        }

    def get_permissions(self):
        return [RoleBasedPermission()]

    def get_queryset(self):
        qs = DepenseVehicule.objects.select_related('vehicule', 'agence')
        return filtrer_par_agence(qs, self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        serializer.save(
            created_by=user,
            agence=agence_pour_creation(user, serializer.validated_data.get('agence'))
        )

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

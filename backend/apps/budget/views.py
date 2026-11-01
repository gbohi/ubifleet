"""UbiFleet — Budget Views"""

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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
    categorie = df.BaseInFilter(field_name='categorie', lookup_expr='in')
    date_min = df.DateFilter(field_name='date_depense', lookup_expr='gte')
    date_max = df.DateFilter(field_name='date_depense', lookup_expr='lte')
    mois = df.NumberFilter(field_name='date_depense__month')
    annee = df.NumberFilter(field_name='date_depense__year')
    poste = df.CharFilter(method='filtrer_poste')
    origine = df.CharFilter(method='filtrer_origine')
    recherche = df.CharFilter(method='filtrer_recherche')

    def filtrer_poste(self, qs, name, value):
        """Poste du budget annuel : les catégories qui y sont imputées."""
        from apps.parametrage.models import CategorieDepense
        return qs.filter(categorie__in=CategorieDepense.objects.filter(poste_budget=value).values('code'))

    def filtrer_origine(self, qs, name, value):
        """« manuelle » ou une source (prise_carburant, intervention, pneu, contrat_assurance, sinistre)."""
        return qs.filter(ref_objet_type='' if value == 'manuelle' else value)

    def filtrer_recherche(self, qs, name, value):
        from django.db.models import Q
        return qs.filter(Q(description__icontains=value) | Q(fournisseur__icontains=value)
                         | Q(numero_facture__icontains=value) | Q(vehicule__immatriculation__icontains=value))

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
            pneumatiques=Sum('budget_pneumatiques'),
            divers=Sum('budget_divers'),
        )
        from apps.parametrage.models import CategorieDepense, libelles
        from .serializers import realise_par_poste
        noms = libelles(CategorieDepense)
        for ligne in par_categorie:
            ligne['libelle'] = noms.get(ligne['categorie'], ligne['categorie'])
        return Response({
            'annee': annee,
            'total_realise': global_agg['total'] or 0,
            'par_categorie': par_categorie,
            'par_mois': par_mois,
            'par_agence': par_agence,
            'top_vehicules': par_vehicule,
            'budgets_prevus': budget_total,
            'realise_par_poste': realise_par_poste(par_categorie),
        })


class DepenseViewSet(viewsets.ModelViewSet):
    serializer_class = DepenseSerializer

    module   = 'budget'
    role_map = {
        'list': 'comptable',
        'retrieve': 'comptable',
        'etat': 'comptable',
        'create': 'responsable_flotte',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'super_admin',
    }

    filter_backends = [DjangoFilterBackend]
    filterset_class = DepenseFilter

    def get_permissions(self):
        return [RoleBasedPermission()]

    def get_queryset(self):
        qs = DepenseVehicule.objects.select_related('vehicule', 'agence').order_by('-date_depense', '-created_at')
        return filtrer_par_agence(qs, self.request.user)

    @action(detail=False, methods=['get'])
    def etat(self, request):
        """État des dépenses (mêmes filtres que la liste) : totaux par catégorie,
        par poste du budget et par origine."""
        from apps.parametrage.models import CategorieDepense
        from .automatiques import ORIGINES
        qs = self.filter_queryset(self.get_queryset()).order_by()
        total = float(qs.aggregate(t=Sum('montant'))['t'] or 0)
        cats = {c.code: c for c in CategorieDepense.objects.all()}
        postes = dict(CategorieDepense.PosteBudget.choices)

        def part(montant):
            return round(montant * 100 / total, 1) if total else 0

        par_categorie, par_poste = [], {}
        for r in qs.values('categorie').annotate(nb=Count('id'), t=Sum('montant')).order_by('-t'):
            c = cats.get(r['categorie'])
            poste = c.poste_budget if c else 'divers'
            montant = float(r['t'] or 0)
            par_categorie.append({'categorie': r['categorie'], 'libelle': c.libelle if c else r['categorie'],
                                  'poste': poste, 'poste_libelle': postes.get(poste, poste),
                                  'nb': r['nb'], 'total': montant, 'part': part(montant)})
            p = par_poste.setdefault(poste, {'poste': poste, 'libelle': postes.get(poste, poste), 'nb': 0, 'total': 0.0})
            p['nb'] += r['nb']
            p['total'] += montant
        for p in par_poste.values():
            p['part'] = part(p['total'])
        par_origine = [{'origine': r['ref_objet_type'] or 'manuelle',
                        'libelle': ORIGINES.get(r['ref_objet_type'], 'Saisie manuelle'),
                        'nb': r['nb'], 'total': float(r['t'] or 0), 'part': part(float(r['t'] or 0))}
                       for r in qs.values('ref_objet_type').annotate(nb=Count('id'), t=Sum('montant')).order_by('-t')]
        return Response({
            'total': total, 'nb': qs.count(),
            'par_categorie': par_categorie,
            'par_poste': sorted(par_poste.values(), key=lambda p: -p['total']),
            'par_origine': par_origine,
        })

    def perform_create(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        serializer.save(
            created_by=user,
            agence=agence_pour_creation(user, serializer.validated_data.get('agence'))
        )

    def _refuser_si_automatique(self, depense):
        from .automatiques import MODIFIER_DANS
        if depense.ref_objet_type in MODIFIER_DANS:
            raise ValidationError({'detail': "Dépense reportée automatiquement : modifiez ou supprimez "
                                             f"{MODIFIER_DANS[depense.ref_objet_type]}."})

    def perform_update(self, serializer):
        self._refuser_si_automatique(serializer.instance)
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    def perform_destroy(self, instance):
        self._refuser_si_automatique(instance)
        instance.delete()

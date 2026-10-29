"""UbiFleet — Entretien Views"""

from rest_framework import viewsets, status, filters
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import F
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone
import datetime

from .models import Intervention, TypeIntervention, Prestataire, SuiviPneus, DocumentIntervention
from .serializers import (
    DocumentInterventionSerializer,
    InterventionSerializer, TypeInterventionSerializer,
    PrestataireSerializer, PneusSerializer
)
from apps.accounts.permissions import IsFleetManager, RoleBasedPermission
from apps.core.agences import (
    AgenceMixin, agence_effective, agence_pour_creation, controler_agence, filtrer_par_agence,
)


class InterventionViewSet(viewsets.ModelViewSet):
    """
    CRUD interventions.
    POST /entretien/interventions/{id}/demarrer/  — changer statut → en_cours
    POST /entretien/interventions/{id}/terminer/  — clôturer avec coût réel
    GET  /entretien/interventions/planifiees/     — calendrier des entretiens à venir
    GET  /entretien/interventions/stats/          — statistiques entretiens
    """
    serializer_class = InterventionSerializer

    module   = 'entretien'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
        'demarrer': 'gestionnaire',
        'terminer': 'gestionnaire',
        'stats': 'operateur',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vehicule', 'agence', 'statut', 'priorite', 'type_intervention']
    search_fields = ['vehicule__immatriculation', 'description', 'prestataire__nom']
    ordering_fields = ['date_planifiee', 'cout_estime', 'priorite', 'created_at']
    ordering = ['-date_planifiee']

    def get_queryset(self):
        qs = Intervention.objects.select_related(
            'vehicule', 'type_intervention', 'prestataire', 'agence'
        )
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

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        intervention = self.get_object()
        if intervention.statut != Intervention.Statut.PLANIFIE:
            return Response(
                {'detail': 'Seules les interventions planifiées peuvent démarrer.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        intervention.statut = Intervention.Statut.EN_COURS
        intervention.date_debut = timezone.now().date()
        intervention.save()
        from apps.parametrage.models import StatutVehicule as _SV
        _sv = _SV.objects.filter(code='en_revision').first()
        if _sv: intervention.vehicule.statut = _sv
        intervention.vehicule.save(update_fields=['statut'])
        return Response({'detail': 'Intervention démarrée.'})

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        intervention = self.get_object()
        cout_reel = request.data.get('cout_reel')
        rapport = request.data.get('rapport', '')
        prochain_km = request.data.get('prochain_km')

        if cout_reel:
            intervention.cout_reel = cout_reel
        if rapport:
            intervention.rapport_intervention = rapport
        if prochain_km:
            intervention.prochain_km = prochain_km
        intervention.statut = Intervention.Statut.TERMINE
        intervention.date_fin = timezone.now().date()
        intervention.save()

        from apps.parametrage.models import StatutVehicule as _SV2
        _sv2 = _SV2.objects.filter(code='en_service').first()
        if _sv2: intervention.vehicule.statut = _sv2
        intervention.vehicule.save(update_fields=['statut'])
        return Response({'detail': 'Intervention terminée.'})

    @action(detail=False, methods=['get'])
    def planifiees(self, request):
        """Interventions à venir dans les 30 prochains jours."""
        horizon = timezone.now().date() + datetime.timedelta(days=30)
        qs = self.get_queryset().filter(
            statut__in=[Intervention.Statut.PLANIFIE, Intervention.Statut.EN_COURS],
            date_planifiee__lte=horizon
        ).order_by('date_planifiee')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        mois = request.query_params.get('mois', timezone.now().month)
        annee = request.query_params.get('annee', timezone.now().year)
        qs_periode = qs.filter(date_planifiee__month=mois, date_planifiee__year=annee)

        return Response({
            'total_periode': qs_periode.count(),
            'terminees': qs_periode.filter(statut='termine').count(),
            'cout_total': qs_periode.filter(statut='termine').aggregate(
                total=Sum('cout_reel')
            )['total'] or 0,
            'par_categorie': list(
                qs_periode.values('type_intervention__categorie')
                          .annotate(count=Count('id'), cout=Sum('cout_reel'))
            ),
            'par_prestataire': list(
                qs_periode.filter(prestataire__isnull=False)
                          .values('prestataire__nom')
                          .annotate(count=Count('id'), cout=Sum('cout_reel'))
                          .order_by('-cout')[:5]
            )
        })


class TypeInterventionViewSet(viewsets.ModelViewSet):
    queryset = TypeIntervention.objects.filter(is_active=True)
    module   = 'parametres'
    serializer_class = TypeInterventionSerializer
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'responsable_flotte',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'responsable_flotte',
    }
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom']
    filterset_fields = ['categorie']


class PrestataireViewSet(AgenceMixin, viewsets.ModelViewSet):
    serializer_class = PrestataireSerializer
    module   = 'parametres'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'ville']
    filterset_fields = ['agence', 'is_active']

    agence_a_la_creation = True

    def get_queryset(self):
        # Prestataires de son agence et prestataires communs (sans agence)
        qs = Prestataire.objects.filter(is_active=True)
        user = self.request.user
        if user.agence_id:
            qs = qs.filter(Q(agence__isnull=True) | Q(agence_id=user.agence_id))
        return qs


class PneusViewSet(AgenceMixin, viewsets.ModelViewSet):
    serializer_class = PneusSerializer
    module   = 'entretien'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
        'a_changer': 'operateur',
    }
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['vehicule', 'statut', 'position']

    champ_agence = 'vehicule__agence'

    def get_queryset(self):
        return self.filtrer_agence(SuiviPneus.objects.select_related('vehicule'))

    @action(detail=False, methods=['get'])
    def a_changer(self, request):
        """Pneus dont l'usure dépasse 85% ou statut à changer."""
        qs = self.get_queryset().filter(
            Q(statut='a_changer') |
            Q(kilometrage_remplacement__lte=F('vehicule__kilometrage_actuel'))
        )
        return Response(self.get_serializer(qs, many=True).data)


# ── URLs ──
"""UbiFleet — Entretien URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter


def get_urlpatterns():
    router = DefaultRouter()
    router.register('interventions', InterventionViewSet, basename='intervention')
    router.register('types', TypeInterventionViewSet, basename='type-intervention')
    router.register('prestataires', PrestataireViewSet, basename='prestataire')
    router.register('pneus', PneusViewSet, basename='pneu')
    return [path('', include(router.urls))]


class DocumentInterventionViewSet(AgenceMixin, viewsets.ModelViewSet):
    """Upload et gestion des documents liés à une intervention."""
    serializer_class   = DocumentInterventionSerializer
    module             = 'entretien'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }
    parser_classes     = [MultiPartParser, FormParser]
    pagination_class   = None

    def get_queryset(self):
        qs = DocumentIntervention.objects.select_related('intervention')
        intervention_id = self.request.query_params.get('intervention') or                           self.kwargs.get('intervention_pk')
        if intervention_id:
            qs = qs.filter(intervention__id=intervention_id)
        type_doc = self.request.query_params.get('type_doc')
        if type_doc:
            qs = qs.filter(type_doc=type_doc)
        return self.filtrer_agence(qs)

    champ_agence = 'intervention__agence'

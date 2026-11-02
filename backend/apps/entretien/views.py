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
from apps.core.referentiels import SuppressionProtegeeMixin, annoter_utilisations
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
        'annuler': 'gestionnaire',
        'stats': 'operateur',
        'synthese': 'operateur',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vehicule', 'agence', 'statut', 'priorite', 'type_intervention', 'prestataire']
    search_fields = ['vehicule__immatriculation', 'description', 'prestataire__nom']
    ordering_fields = ['date_planifiee', 'cout_estime', 'priorite', 'created_at']
    ordering = ['-date_planifiee']

    def get_queryset(self):
        qs = Intervention.objects.select_related(
            'vehicule', 'type_intervention', 'prestataire', 'agence'
        ).prefetch_related('documents')
        q = self.request.query_params
        if q.get('date_debut'):  qs = qs.filter(date_planifiee__gte=q['date_debut'])
        if q.get('date_fin'):    qs = qs.filter(date_planifiee__lte=q['date_fin'])
        if q.get('categorie'):   qs = qs.filter(type_intervention__categorie=q['categorie'])
        if q.get('ouvertes'):    qs = qs.filter(statut__in=['planifie', 'en_cours', 'attente_piece'])
        if q.get('en_retard'):   qs = qs.filter(statut='planifie', date_planifiee__lt=timezone.localdate())
        return filtrer_par_agence(qs, self.request.user)

    def _controler_vehicule(self, vehicule):
        """Le véhicule doit être visible par l'utilisateur ; l'intervention prend son agence."""
        from rest_framework.exceptions import PermissionDenied
        from apps.vehicules.models import Vehicule
        if not filtrer_par_agence(Vehicule.objects.filter(pk=vehicule.pk), self.request.user).exists():
            raise PermissionDenied("Ce véhicule n'est pas de votre agence.")
        return vehicule.agence

    def perform_create(self, serializer):
        user = self.request.user
        vehicule = serializer.validated_data['vehicule']
        extra = {}
        if serializer.validated_data.get('statut') == Intervention.Statut.EN_COURS:
            extra['date_debut'] = serializer.validated_data.get('date_debut') or timezone.localdate()
        intervention = serializer.save(created_by=user, agence=self._controler_vehicule(vehicule), **extra)
        if intervention.statut == Intervention.Statut.EN_COURS:
            self._vehicule_en_revision(intervention, user)

    def perform_update(self, serializer):
        vehicule = serializer.validated_data.get('vehicule', serializer.instance.vehicule)
        ancien = serializer.instance.statut
        intervention = serializer.save(agence=self._controler_vehicule(vehicule))
        if intervention.statut == Intervention.Statut.EN_COURS and ancien != intervention.statut:
            if not intervention.date_debut:
                Intervention.objects.filter(pk=intervention.pk).update(date_debut=timezone.localdate())
            self._vehicule_en_revision(intervention, self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Seule une intervention planifiée (ou annulée) se supprime ; une intervention
        commencée ou terminée s'annule ou reste dans l'historique."""
        intervention = self.get_object()
        if intervention.statut not in (Intervention.Statut.PLANIFIE, Intervention.Statut.ANNULE):
            return Response({'detail': "Intervention commencée ou terminée : elle ne se supprime pas "
                                       "(annulez-la si elle n'a pas eu lieu)."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    # ── Statut du véhicule pendant l'intervention (historisé) ──
    @staticmethod
    def _vehicule_en_revision(intervention, user):
        from apps.vehicules.models import changer_statut_vehicule
        changer_statut_vehicule(intervention.vehicule, 'en_revision',
                                f"Intervention « {intervention.type_intervention.nom} » démarrée.",
                                user, intervention.date_debut)

    @staticmethod
    def _vehicule_remis_en_service(intervention, user, motif):
        """Remis « En service » s'il était « En révision » et n'a plus d'intervention en cours."""
        from apps.vehicules.models import changer_statut_vehicule
        v = intervention.vehicule
        autres = Intervention.objects.filter(vehicule=v, statut__in=['en_cours', 'attente_piece']).exclude(pk=intervention.pk)
        if v.statut and v.statut.code == 'en_revision' and not autres.exists():
            changer_statut_vehicule(v, 'en_service', motif, user)

    @staticmethod
    def _date(valeur, defaut):
        if not valeur:
            return defaut
        try:
            return datetime.date.fromisoformat(str(valeur)[:10])
        except ValueError:
            return None

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """Intervention planifiée → en cours (date de début saisie, aujourd'hui par défaut) ;
        le véhicule passe « En révision » (historisé)."""
        intervention = self.get_object()
        if intervention.statut != Intervention.Statut.PLANIFIE:
            return Response({'detail': 'Seules les interventions planifiées peuvent démarrer.'},
                            status=status.HTTP_400_BAD_REQUEST)
        jour = self._date(request.data.get('date_debut'), timezone.localdate())
        if not jour or jour > timezone.localdate():
            return Response({'detail': 'Date de début invalide (elle ne peut pas être dans le futur).'},
                            status=status.HTTP_400_BAD_REQUEST)
        intervention.statut = Intervention.Statut.EN_COURS
        intervention.date_debut = jour
        intervention.save()
        self._vehicule_en_revision(intervention, request.user)
        return Response(self.get_serializer(intervention).data)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """Clôture : coût réel (obligatoire), date de fin, rapport, km et prochain km
        de révision ; le véhicule est remis « En service » s'il n'a plus
        d'intervention en cours. Le coût réel est reporté dans les dépenses."""
        intervention = self.get_object()
        if intervention.statut in (Intervention.Statut.TERMINE, Intervention.Statut.ANNULE):
            return Response({'detail': 'Intervention déjà terminée ou annulée.'}, status=status.HTTP_400_BAD_REQUEST)
        from decimal import Decimal, InvalidOperation
        erreurs = {}
        try:
            cout = Decimal(str(request.data.get('cout_reel', '')).replace(',', '.').replace(' ', ''))
            if cout < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            erreurs['cout_reel'] = 'Saisissez le coût réel (0 ou plus).'
            cout = None
        aujourd_hui = timezone.localdate()
        debut = intervention.date_debut or intervention.date_planifiee
        fin = self._date(request.data.get('date_fin'), aujourd_hui)
        if not fin or fin > aujourd_hui:
            erreurs['date_fin'] = "La date de fin ne peut pas être dans le futur."
        elif fin < debut and intervention.date_debut:
            erreurs['date_fin'] = f"La date de fin précède le début de l'intervention ({debut:%d/%m/%Y})."
        km = request.data.get('kilometrage_intervention')
        prochain = request.data.get('prochain_km')
        try:
            km = int(km) if km not in (None, '') else intervention.kilometrage_intervention
            prochain = int(prochain) if prochain not in (None, '') else None
        except (TypeError, ValueError):
            erreurs['prochain_km'] = 'Kilométrage invalide.'
        else:
            reference = max(km or 0, intervention.vehicule.kilometrage_actuel or 0)
            if prochain is not None and prochain <= reference:
                erreurs['prochain_km'] = (f"Le prochain entretien doit être au-delà du kilométrage actuel "
                                          f"({reference:,} km).".replace(',', ' '))
        if erreurs:
            return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)
        intervention.cout_reel = cout
        intervention.rapport_intervention = request.data.get('rapport', '') or intervention.rapport_intervention
        intervention.kilometrage_intervention = km
        if prochain is not None:
            intervention.prochain_km = prochain
        intervention.date_debut = intervention.date_debut or min(fin, intervention.date_planifiee)
        intervention.date_fin = fin
        intervention.statut = Intervention.Statut.TERMINE
        intervention.save()
        self._vehicule_remis_en_service(intervention, request.user,
                                        f"Intervention « {intervention.type_intervention.nom} » terminée.")
        return Response(self.get_serializer(intervention).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """Annulation (motif obligatoire) d'une intervention non terminée."""
        intervention = self.get_object()
        if intervention.statut in (Intervention.Statut.TERMINE, Intervention.Statut.ANNULE):
            return Response({'detail': 'Intervention déjà terminée ou annulée.'}, status=status.HTTP_400_BAD_REQUEST)
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response({'motif': "Indiquez le motif de l'annulation."}, status=status.HTTP_400_BAD_REQUEST)
        intervention.statut = Intervention.Statut.ANNULE
        intervention.rapport_intervention = (f"Annulée le {timezone.localdate():%d/%m/%Y} : {motif}\n"
                                             + (intervention.rapport_intervention or '')).strip()
        intervention.save()
        self._vehicule_remis_en_service(intervention, request.user,
                                        f"Intervention « {intervention.type_intervention.nom} » annulée.")
        return Response(self.get_serializer(intervention).data)

    @action(detail=False, methods=['get'])
    def synthese(self, request):
        """Compteurs de toutes les interventions filtrées (agence, recherche, période),
        et non de la seule page affichée."""
        qs = self.filter_queryset(self.get_queryset()).order_by()
        par_statut = dict(qs.values_list('statut').annotate(n=Count('id')))
        ouvertes = qs.filter(statut__in=['planifie', 'en_cours', 'attente_piece'])
        pneus = SuiviPneus.objects.exclude(statut='change').filter(
            Q(statut='a_changer') | Q(kilometrage_remplacement__lte=F('vehicule__kilometrage_actuel')))
        pneus = filtrer_par_agence(pneus, request.user, 'vehicule__agence')
        if request.query_params.get('agence'):
            pneus = pneus.filter(vehicule__agence=request.query_params['agence'])
        return Response({
            'total': qs.count(),
            'par_statut': {code: par_statut.get(code, 0) for code, _ in Intervention.Statut.choices},
            'urgentes': ouvertes.filter(priorite__in=['critique', 'haute']).count(),
            'en_retard': qs.filter(statut='planifie', date_planifiee__lt=timezone.localdate()).count(),
            'cout_estime_ouvertes': float(ouvertes.aggregate(t=Sum('cout_estime'))['t'] or 0),
            'cout_reel_terminees': float(qs.filter(statut='termine').aggregate(t=Sum('cout_reel'))['t'] or 0),
            'pneus_a_changer': pneus.count(),
        })

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


class TypeInterventionViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    relations_utilisation = [('interventions', 'intervention(s)')]
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

    def get_queryset(self):
        qs = annoter_utilisations(TypeIntervention.objects.all(), 'interventions')
        # Listes : éléments actifs, sauf ?tous=1 (page Paramètres)
        if self.action == 'list' and not self.request.query_params.get('tous'):
            qs = qs.filter(is_active=True)
        return qs


class PrestataireViewSet(SuppressionProtegeeMixin, AgenceMixin, viewsets.ModelViewSet):
    relations_utilisation = [('interventions', 'intervention(s)')]
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
        qs = annoter_utilisations(Prestataire.objects.all(), 'interventions')
        # Listes : éléments actifs, sauf ?tous=1 (page Paramètres)
        if self.action == 'list' and not self.request.query_params.get('tous'):
            qs = qs.filter(is_active=True)
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
        qs = self.get_queryset().exclude(statut='change').filter(
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

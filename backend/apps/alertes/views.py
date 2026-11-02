"""UbiFleet — Alertes Views"""

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.permissions import RoleBasedPermission
from apps.core.agences import controler_agence, voit_toutes_agences
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from django.utils import timezone

from .models import Alerte
from .serializers import AlerteSerializer


def alertes_visibles(user, qs=None):
    """Alertes qu'un utilisateur voit : les alertes générales de son agence
    (toutes s'il voit toutes les agences) et celles qui lui sont adressées
    personnellement — jamais celles adressées à un autre utilisateur."""
    from django.db.models import Q
    qs = Alerte.objects.all() if qs is None else qs
    filtre_general = Q(destinataire__isnull=True)
    if not voit_toutes_agences(user):
        filtre_general &= Q(agence_id=user.agence_id)
    return qs.filter(filtre_general | Q(destinataire=user))


class AlerteViewSet(viewsets.ModelViewSet):
    """
    Centre d'alertes UbiFleet.
    GET  /alertes/?statut=active          — alertes actives
    POST /alertes/{id}/traiter/           — marquer comme traitée
    POST /alertes/{id}/ignorer/           — ignorer l'alerte
    POST /alertes/marquer_toutes_lues/    — tout marquer comme lu
    GET  /alertes/resume/                 — résumé par type et priorité
    """
    serializer_class = AlerteSerializer
    module   = 'alertes'
    permission_classes = [RoleBasedPermission]
    # Consultation et traitement : tout utilisateur, sur ses alertes (agence
    # ou personnelles, cf. get_queryset). Création / modification /
    # suppression manuelles et génération globale : responsable flotte.
    role_map = {
        'list': 'chauffeur',
        'retrieve': 'chauffeur',
        'resume': 'chauffeur',
        'types': 'chauffeur',
        'traiter': 'chauffeur',
        'ignorer': 'chauffeur',
        'marquer_toutes_lues': 'chauffeur',
        'create': 'responsable_flotte',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'responsable_flotte',
        'generer': 'responsable_flotte',
    }
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['agence', 'type_alerte', 'priorite', 'vehicule', 'chauffeur']
    search_fields = ['titre', 'message', 'vehicule__immatriculation', 'chauffeur__nom', 'chauffeur__prenom']
    ordering_fields = ['created_at', 'rang', 'date_echeance']
    # Les plus prioritaires d'abord, puis les plus récentes
    ordering = ['rang', '-created_at']

    def get_queryset(self):
        from django.db.models import Case, IntegerField, Value, When
        qs = alertes_visibles(self.request.user).select_related(
            'vehicule', 'chauffeur', 'agence', 'traitee_par', 'destinataire'
        ).annotate(rang=Case(
            When(priorite='critique', then=Value(0)), When(priorite='haute', then=Value(1)),
            When(priorite='normale', then=Value(2)), default=Value(3), output_field=IntegerField()))
        p = self.request.query_params
        # statut : un statut, ou « a_traiter » (actives et lues)
        statut = p.get('statut')
        if statut == 'a_traiter':
            qs = qs.filter(statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE])
        elif statut:
            qs = qs.filter(statut=statut)
        if p.get('date_debut'):
            qs = qs.filter(created_at__date__gte=p['date_debut'])
        if p.get('date_fin'):
            qs = qs.filter(created_at__date__lte=p['date_fin'])
        return qs

    def perform_create(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    @action(detail=True, methods=['post'])
    def traiter(self, request, pk=None):
        alerte = self.get_object()
        if alerte.statut in (Alerte.Statut.TRAITEE, Alerte.Statut.IGNOREE):
            return Response({'detail': 'Cette alerte est déjà close.'}, status=400)
        alerte.statut = Alerte.Statut.TRAITEE
        alerte.traitee_par = request.user
        alerte.date_traitement = timezone.now()
        alerte.notes_traitement = request.data.get('notes', '')
        alerte.save()
        return Response({'detail': 'Alerte marquée comme traitée.'})

    @action(detail=True, methods=['post'])
    def ignorer(self, request, pk=None):
        alerte = self.get_object()
        if alerte.statut in (Alerte.Statut.TRAITEE, Alerte.Statut.IGNOREE):
            return Response({'detail': 'Cette alerte est déjà close.'}, status=400)
        alerte.statut = Alerte.Statut.IGNOREE
        alerte.traitee_par = request.user
        alerte.date_traitement = timezone.now()
        alerte.save()
        return Response({'detail': 'Alerte ignorée.'})

    @action(detail=False, methods=['post'])
    def generer(self, request):
        """Déclenche la vérification de toutes les alertes (sans Celery)."""
        from apps.alertes.tasks import run_all_checks_sync
        run_all_checks_sync()
        nb = Alerte.objects.filter(statut=Alerte.Statut.ACTIVE).count()
        return Response({'detail': 'Alertes générées.', 'total_actives': nb})

    @action(detail=False, methods=['post'])
    def marquer_toutes_lues(self, request):
        updated = self.get_queryset().filter(
            statut=Alerte.Statut.ACTIVE
        ).update(statut=Alerte.Statut.LUE)
        return Response({'detail': f'{updated} alertes marquées comme lues.'})

    @action(detail=False, methods=['get'])
    def types(self, request):
        """Types d'alerte (code, libellé) pour le filtre."""
        from .serializers import LIBELLES_TYPES
        return Response([{'code': c, 'libelle': l} for c, l in sorted(LIBELLES_TYPES.items(), key=lambda x: x[1])])

    @action(detail=False, methods=['get'])
    def resume(self, request):
        """Alertes à traiter (actives et lues) : total, non lues, par priorité."""
        qs = alertes_visibles(request.user).filter(statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE])
        return Response({
            'total': qs.count(),
            'total_actives': qs.filter(statut=Alerte.Statut.ACTIVE).count(),
            'non_lues': qs.filter(statut=Alerte.Statut.ACTIVE).count(),
            'critiques': qs.filter(priorite='critique').count(),
            'hautes': qs.filter(priorite='haute').count(),
            'normales': qs.filter(priorite='normale').count(),
            'basses': qs.filter(priorite='basse').count(),
            'par_type': list(
                qs.values('type_alerte').annotate(count=Count('id'))
            ),
            'par_agence': list(
                qs.values('agence__nom', 'agence__code')
                  .annotate(count=Count('id'))
            ),
        })

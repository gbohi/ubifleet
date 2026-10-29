"""UbiFleet — Alertes Views"""

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from django.utils import timezone

from .models import Alerte
from .serializers import AlerteSerializer


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
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['agence', 'type_alerte', 'priorite', 'statut', 'vehicule']
    ordering_fields = ['created_at', 'priorite', 'date_echeance']
    ordering = ['-created_at']

    def get_queryset(self):
        from django.db.models import Q
        qs = Alerte.objects.select_related(
            'vehicule', 'chauffeur', 'agence', 'traitee_par', 'destinataire'
        )
        user = self.request.user

        # Alertes générales (existantes) : filtrées par agence comme avant
        filtre_general = Q(destinataire__isnull=True)
        if not user.is_admin_level() and user.agence:
            filtre_general &= Q(agence=user.agence)

        # Alertes personnelles (nouvelles) : ciblées vers cet utilisateur
        filtre_personnel = Q(destinataire=user)

        return qs.filter(filtre_general | filtre_personnel)

    @action(detail=True, methods=['post'])
    def traiter(self, request, pk=None):
        alerte = self.get_object()
        alerte.statut = Alerte.Statut.TRAITEE
        alerte.traitee_par = request.user
        alerte.date_traitement = timezone.now()
        alerte.notes_traitement = request.data.get('notes', '')
        alerte.save()
        return Response({'detail': 'Alerte marquée comme traitée.'})

    @action(detail=True, methods=['post'])
    def ignorer(self, request, pk=None):
        alerte = self.get_object()
        alerte.statut = Alerte.Statut.IGNOREE
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
    def resume(self, request):
        qs = self.get_queryset().filter(statut=Alerte.Statut.ACTIVE)
        return Response({
            'total_actives': qs.count(),
            'critiques': qs.filter(priorite='critique').count(),
            'hautes': qs.filter(priorite='haute').count(),
            'normales': qs.filter(priorite='normale').count(),
            'par_type': list(
                qs.values('type_alerte').annotate(count=Count('id'))
            ),
            'par_agence': list(
                qs.values('agence__nom', 'agence__code')
                  .annotate(count=Count('id'))
            ),
        })

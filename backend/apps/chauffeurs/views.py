"""UbiFleet — Chauffeurs Views"""

import datetime
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.permissions import RoleBasedPermission
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Count

from .models import Chauffeur
from .serializers import ChauffeurSerializer


class ChauffeurViewSet(viewsets.ModelViewSet):
    """
    CRUD chauffeurs.
    GET  /chauffeurs/permis_expirant/          — permis expirant dans 60 jours
    GET  /chauffeurs/{id}/historique_conduite/ — historique pleins + sinistres
    """
    serializer_class = ChauffeurSerializer

    module   = 'chauffeurs'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
        'permis_expirant': 'operateur',
        'historique_conduite': 'operateur',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['agence', 'statut']
    search_fields = ['nom', 'prenom', 'matricule', 'numero_permis']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_expiration_permis']
    ordering = ['nom', 'prenom']

    def get_queryset(self):
        qs = Chauffeur.objects.select_related('agence', 'user').prefetch_related('vehicule_attitré')
        user = self.request.user
        if not user.is_admin_level() and user.agence:
            qs = qs.filter(agence=user.agence)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def permis_expirant(self, request):
        """Chauffeurs dont le permis expire dans les 60 prochains jours."""
        horizon = timezone.now().date() + datetime.timedelta(days=60)
        qs = self.get_queryset().filter(
            date_expiration_permis__lte=horizon,
            date_expiration_permis__gte=timezone.now().date(),
            statut=Chauffeur.Statut.ACTIF
        ).order_by('date_expiration_permis')
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def historique_conduite(self, request, pk=None):
        """Historique des pleins et sinistres imputés au chauffeur."""
        chauffeur = self.get_object()
        from apps.carburant.models import PleinsCarburant
        from apps.sinistres.models import Sinistre

        pleins_stats = PleinsCarburant.objects.filter(chauffeur=chauffeur).aggregate(
            nb=Count('id'),
            total_litres=Sum('volume_litres'),
            total_montant=Sum('montant_fcfa')
        )
        sinistres = Sinistre.objects.filter(chauffeur=chauffeur).values(
            'numero_dossier', 'type_sinistre', 'date_sinistre', 'statut'
        )

        return Response({
            'chauffeur': self.get_serializer(chauffeur).data,
            'pleins': pleins_stats,
            'sinistres': list(sinistres),
            'nb_sinistres': sinistres.count(),
        })

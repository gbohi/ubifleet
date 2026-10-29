"""UbiFleet — Sinistres Views"""

import datetime
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import RoleBasedPermission
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count
from django.utils import timezone

from .models import Sinistre, ContratAssurance, Assureur
from .serializers import SinistreSerializer, ContratAssuranceSerializer, AssureurSerializer


class SinistreViewSet(viewsets.ModelViewSet):
    """
    CRUD sinistres.
    POST /sinistres/{id}/changer_statut/ — changer le statut du dossier
    GET  /sinistres/stats/               — statistiques sinistres
    """
    serializer_class = SinistreSerializer

    module   = 'sinistres'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
        'changer_statut': 'gestionnaire',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vehicule', 'agence', 'type_sinistre', 'statut']
    search_fields = ['numero_dossier', 'vehicule__immatriculation', 'description']
    ordering_fields = ['date_sinistre', 'created_at']
    ordering = ['-date_sinistre']

    def get_queryset(self):
        qs = Sinistre.objects.select_related(
            'vehicule', 'chauffeur', 'contrat_assurance', 'agence'
        ).prefetch_related('pièces_jointes')
        user = self.request.user
        if not user.is_admin_level() and user.agence:
            qs = qs.filter(agence=user.agence)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            agence=serializer.validated_data.get('agence') or self.request.user.agence
        )

    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
        sinistre = self.get_object()
        new_statut = request.data.get('statut')
        if new_statut not in dict(Sinistre.Statut.choices):
            return Response(
                {'detail': 'Statut invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        sinistre.statut = new_statut
        if new_statut == Sinistre.Statut.CLOS:
            sinistre.date_cloture = timezone.now().date()
        sinistre.save()
        return Response({'detail': f"Statut mis à jour : {sinistre.get_statut_display()}"})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        annee = int(request.query_params.get('annee', timezone.now().year))
        qs_annee = qs.filter(date_sinistre__year=annee)
        return Response({
            'total_annee': qs_annee.count(),
            'en_cours': qs.filter(
                statut__in=['declare', 'en_instruction', 'expertise', 'reparation']
            ).count(),
            'indemnisations': qs_annee.aggregate(
                total=Sum('indemnisation_recue')
            )['total'] or 0,
            'cout_reparations': qs_annee.aggregate(
                total=Sum('cout_reparation')
            )['total'] or 0,
            'par_type': list(qs_annee.values('type_sinistre').annotate(count=Count('id'))),
            'par_agence': list(
                qs_annee.values('agence__nom', 'agence__code')
                        .annotate(count=Count('id'))
            ),
        })


class ContratAssuranceViewSet(viewsets.ModelViewSet):
    """
    CRUD contrats d'assurance.
    GET /contrats/expirant_bientot/ — contrats expirant dans 30 jours
    GET /contrats/expires/          — contrats déjà expirés
    """
    serializer_class = ContratAssuranceSerializer

    module   = 'sinistres'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vehicule', 'assureur', 'type_contrat', 'is_active']
    search_fields = ['numero_police', 'vehicule__immatriculation']

    def get_queryset(self):
        return ContratAssurance.objects.select_related('vehicule', 'assureur')

    @action(detail=False, methods=['get'])
    def expirant_bientot(self, request):
        horizon = timezone.now().date() + datetime.timedelta(days=30)
        qs = self.get_queryset().filter(
            date_fin__lte=horizon,
            date_fin__gte=timezone.now().date(),
            is_active=True
        ).order_by('date_fin')
        return Response(ContratAssuranceSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def expires(self, request):
        qs = self.get_queryset().filter(
            date_fin__lt=timezone.now().date(),
            is_active=True
        ).order_by('-date_fin')
        return Response(ContratAssuranceSerializer(qs, many=True).data)


class AssureurViewSet(viewsets.ModelViewSet):
    queryset = Assureur.objects.filter(is_active=True)
    serializer_class = AssureurSerializer
    module   = 'sinistres'
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom']

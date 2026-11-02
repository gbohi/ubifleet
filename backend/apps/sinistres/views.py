"""UbiFleet — Sinistres Views"""

import datetime
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import RoleBasedPermission
from apps.core.referentiels import SuppressionProtegeeMixin, annoter_utilisations
from apps.core.agences import (
    AgenceMixin, agence_effective, agence_pour_creation, controler_agence, filtrer_par_agence,
)
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count
from django.utils import timezone

from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import Sinistre, ContratAssurance, Assureur, PieceJointeSinistre
from .serializers import SinistreSerializer, ContratAssuranceSerializer, AssureurSerializer, PieceJointeSerializer

STATUTS_CLOTURE = ('indemnise', 'clos')


def controler_vehicule(user, vehicule):
    """Véhicule visible par l'utilisateur ; renvoie son agence (celle du dossier)."""
    from apps.vehicules.models import Vehicule
    if not filtrer_par_agence(Vehicule.objects.filter(pk=vehicule.pk), user).exists():
        raise PermissionDenied("Ce véhicule n'est pas de votre agence.")
    return vehicule.agence


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
        return filtrer_par_agence(qs, self.request.user)

    def perform_create(self, serializer):
        vehicule = serializer.validated_data['vehicule']
        serializer.save(created_by=self.request.user, agence=controler_vehicule(self.request.user, vehicule))

    def perform_update(self, serializer):
        vehicule = serializer.validated_data.get('vehicule', serializer.instance.vehicule)
        serializer.save(agence=controler_vehicule(self.request.user, vehicule))

    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
        """Change le statut du dossier ; « Indemnisé » et « Clos » posent la date de
        clôture (retirée si le dossier est rouvert). Une note facultative est
        ajoutée à l'historique des notes du dossier."""
        sinistre = self.get_object()
        new_statut = request.data.get('statut')
        if new_statut not in dict(Sinistre.Statut.choices):
            return Response({'detail': 'Statut invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_statut == sinistre.statut:
            return Response({'detail': "C'est déjà le statut du dossier."}, status=status.HTTP_400_BAD_REQUEST)
        ancien = sinistre.get_statut_display()
        sinistre.statut = new_statut
        sinistre.date_cloture = (sinistre.date_cloture or timezone.localdate()) if new_statut in STATUTS_CLOTURE else None
        note = (request.data.get('notes') or '').strip()
        auteur = request.user.get_full_name() or request.user.email
        ligne = f"[{timezone.localdate():%d/%m/%Y} — {auteur}] {ancien} → {sinistre.get_statut_display()}" + (f" : {note}" if note else '')
        sinistre.notes = f"{ligne}\n{sinistre.notes}".strip()
        sinistre.save()
        return Response(self.get_serializer(sinistre).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from apps.parametrage.models import TypeSinistre, libelles
        qs = self.filter_queryset(self.get_queryset()).order_by()
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
            'par_type': [{**r, 'libelle': libelles(TypeSinistre).get(r['type_sinistre'], r['type_sinistre'])}
                         for r in qs_annee.values('type_sinistre').annotate(count=Count('id'))],
            'nb_total': qs.count(),
            'par_agence': list(
                qs_annee.values('agence__nom', 'agence__code')
                        .annotate(count=Count('id'))
            ),
        })


class ContratAssuranceViewSet(AgenceMixin, viewsets.ModelViewSet):
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

    champ_agence = 'vehicule__agence'

    def get_queryset(self):
        return self.filtrer_agence(ContratAssurance.objects.select_related('vehicule', 'assureur'))

    def perform_create(self, serializer):
        controler_vehicule(self.request.user, serializer.validated_data['vehicule'])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        controler_vehicule(self.request.user, serializer.validated_data.get('vehicule', serializer.instance.vehicule))
        serializer.save()

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


class AssureurViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    relations_utilisation = [('contrats', "contrat(s) d'assurance")]
    serializer_class = AssureurSerializer
    module   = 'sinistres'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom']

    def get_queryset(self):
        qs = annoter_utilisations(Assureur.objects.all(), 'contrats')
        # Listes : éléments actifs, sauf ?tous=1 (page Paramètres)
        if self.action == 'list' and not self.request.query_params.get('tous'):
            qs = qs.filter(is_active=True)
        return qs


class PieceJointeSinistreViewSet(viewsets.ModelViewSet):
    """Pièces jointes d'un sinistre (?sinistre=<id>) : constat, photos, factures,
    rapport d'expertise… (PDF, images, bureautique ; 10 Mo)."""
    serializer_class = PieceJointeSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    module   = 'sinistres'
    role_map = {'list': 'operateur', 'retrieve': 'operateur', 'create': 'gestionnaire',
                'update': 'gestionnaire', 'partial_update': 'gestionnaire', 'destroy': 'gestionnaire'}
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sinistre', 'type_document']
    pagination_class = None

    def get_permissions(self):
        return [RoleBasedPermission()]

    def get_queryset(self):
        return filtrer_par_agence(PieceJointeSinistre.objects.select_related('sinistre').order_by('-created_at'),
                                  self.request.user, 'sinistre__agence')

    def perform_create(self, serializer):
        sinistre = serializer.validated_data['sinistre']
        if not filtrer_par_agence(Sinistre.objects.filter(pk=sinistre.pk), self.request.user).exists():
            raise PermissionDenied("Ce sinistre n'est pas de votre agence.")
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        nom = instance.fichier.name
        instance.delete()
        if nom:
            instance.fichier.storage.delete(nom)

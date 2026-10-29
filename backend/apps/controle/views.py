"""UbiFleet — Contrôle Véhicule Views"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from django.utils import timezone

from .models import ElementControle, FicheControle, PointControleDetail, PhotoControle
from .serializers import (
    ElementControleSerializer, FicheControleListSerializer,
    FicheControleDetailSerializer, FicheControleWriteSerializer,
    PointControleDetailSerializer, PhotoControleSerializer,
)


class ElementControleViewSet(viewsets.ModelViewSet):
    """CRUD éléments de contrôle — référentiel configurable."""
    serializer_class   = ElementControleSerializer
    pagination_class   = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ElementControle.objects.all()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() == 'true')
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs


class FicheControleViewSet(viewsets.ModelViewSet):
    """CRUD fiches de contrôle."""
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['vehicule', 'agence', 'type_controle', 'statut_global', 'chauffeur']
    ordering_fields    = ['date_heure', 'kilometrage', 'created_at']
    ordering           = ['-date_heure']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FicheControleWriteSerializer
        if self.action == 'retrieve':
            return FicheControleDetailSerializer
        return FicheControleListSerializer

    def get_queryset(self):
        qs = FicheControle.objects.select_related(
            'vehicule', 'chauffeur', 'agence', 'created_by'
        ).prefetch_related('points', 'photos')
        user = self.request.user
        if not user.is_admin_level() and user.agence:
            qs = qs.filter(agence=user.agence)

        # Filtres additionnels
        date_debut = self.request.query_params.get('date_debut')
        date_fin   = self.request.query_params.get('date_fin')
        immat      = self.request.query_params.get('immatriculation')
        if date_debut: qs = qs.filter(date_heure__date__gte=date_debut)
        if date_fin:   qs = qs.filter(date_heure__date__lte=date_fin)
        if immat:      qs = qs.filter(vehicule__immatriculation__icontains=immat)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        agence = serializer.validated_data.get('agence') or getattr(user, 'agence', None)
        serializer.save(created_by=user, agence=agence)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Finalise la fiche et calcule le statut global."""
        fiche = self.get_object()
        fiche.statut_global = fiche.calculer_statut_global()
        fiche.save()
        return Response({'statut_global': fiche.statut_global,
                         'statut_display': fiche.get_statut_global_display()})

    @action(detail=True, methods=['get'])
    def rapport(self, request, pk=None):
        """Rapport complet d'une fiche avec statistiques."""
        fiche = self.get_object()
        points = fiche.points.select_related('element')
        par_categorie = {}
        for p in points:
            cat = p.element.categorie
            if cat not in par_categorie:
                par_categorie[cat] = {'total': 0, 'conformes': 0, 'non_conformes': 0, 'na': 0}
            par_categorie[cat]['total'] += 1
            par_categorie[cat][p.statut + 's'] += 1

        return Response({
            'fiche': FicheControleDetailSerializer(fiche).data,
            'statistiques': {
                'total_points':    points.count(),
                'conformes':       points.filter(statut='conforme').count(),
                'non_conformes':   points.filter(statut='non_conforme').count(),
                'na':              points.filter(statut='na').count(),
                'bloquants':       points.filter(gravite='bloquant').count(),
                'majeurs':         points.filter(gravite='majeur').count(),
                'par_categorie':   par_categorie,
            },
            'photos': PhotoControleSerializer(fiche.photos.all(), many=True).data,
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques globales des contrôles."""
        qs = self.get_queryset()
        return Response({
            'total':        qs.count(),
            'conformes':    qs.filter(statut_global='conforme').count(),
            'non_conformes':qs.filter(statut_global='non_conforme').count(),
            'en_cours':     qs.filter(statut_global='en_cours').count(),
            'par_type':     list(qs.values('type_controle')
                                    .annotate(nb=Count('id')).order_by('-nb')),
        })


class PointControleDetailViewSet(viewsets.ModelViewSet):
    """CRUD points de contrôle d'une fiche."""
    serializer_class   = PointControleDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = None

    def get_queryset(self):
        qs = PointControleDetail.objects.select_related('element', 'fiche')
        fiche_id = self.request.query_params.get('fiche')
        if fiche_id:
            qs = qs.filter(fiche__id=fiche_id)
        return qs

    def perform_create(self, serializer):
        point = serializer.save()
        # Recalculer le statut global de la fiche
        fiche = point.fiche
        fiche.statut_global = fiche.calculer_statut_global()
        fiche.save()

    @action(detail=False, methods=['post'])
    def bulk_save(self, request):
        """Sauvegarde plusieurs points en une seule requête."""
        fiche_id = request.data.get('fiche_id')
        points   = request.data.get('points', [])
        if not fiche_id:
            return Response({'detail': 'fiche_id requis.'}, status=400)
        try:
            fiche = FicheControle.objects.get(id=fiche_id)
        except FicheControle.DoesNotExist:
            return Response({'detail': 'Fiche introuvable.'}, status=404)

        saved = []
        for p in points:
            element_id = p.get('element')
            statut     = p.get('statut', 'conforme')
            gravite    = p.get('gravite') if statut == 'non_conforme' else None
            remarque   = p.get('remarque', '')
            obj, _ = PointControleDetail.objects.update_or_create(
                fiche=fiche, element_id=element_id,
                defaults={'statut': statut, 'gravite': gravite, 'remarque': remarque}
            )
            saved.append(obj.id)

        # Recalculer statut global
        fiche.statut_global = fiche.calculer_statut_global()
        fiche.save()

        return Response({'saved': len(saved), 'statut_global': fiche.statut_global})


class PhotoControleViewSet(viewsets.ModelViewSet):
    """Upload / suppression des photos d'une fiche."""
    serializer_class   = PhotoControleSerializer
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    pagination_class   = None

    def get_queryset(self):
        qs = PhotoControle.objects.all()
        fiche_id = self.request.query_params.get('fiche')
        if fiche_id:
            qs = qs.filter(fiche__id=fiche_id)
        return qs

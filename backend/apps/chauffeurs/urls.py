from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import serializers, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Chauffeur


class ChauffeurSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    permis_expire = serializers.BooleanField(read_only=True)
    jours_expiration_permis = serializers.IntegerField(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)
    vehicule_actuel = serializers.SerializerMethodField()

    class Meta:
        model = Chauffeur
        fields = [
            'id', 'matricule', 'nom', 'prenom', 'nom_complet',
            'date_naissance', 'telephone', 'email', 'adresse', 'photo',
            'numero_permis', 'categories_permis',
            'date_obtention_permis', 'date_expiration_permis',
            'permis_expire', 'jours_expiration_permis',
            'agence', 'agence_nom', 'statut', 'statut_display',
            'vehicule_actuel', 'notes', 'created_at'
        ]

    def get_vehicule_actuel(self, obj):
        try:
            v = obj.vehicule_attitré
            if v is None:
                return None
            # vehicule_attitré est une RelatedManager (reverse FK)
            # on prend le premier véhicule attitré s'il existe
            if hasattr(v, 'all'):
                v = v.first()
            if v is None:
                return None
            return {
                'id': str(v.id),
                'immatriculation': v.immatriculation,
                'designation': v.designation
            }
        except Exception:
            return None


class ChauffeurViewSet(viewsets.ModelViewSet):
    serializer_class = ChauffeurSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['agence', 'statut']
    search_fields = ['nom', 'prenom', 'matricule', 'numero_permis']
    ordering = ['nom', 'prenom']

    def get_queryset(self):
        qs = Chauffeur.objects.select_related('agence')
        user = self.request.user
        if not user.is_admin_level() and user.agence:
            qs = qs.filter(agence=user.agence)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def permis_expirant(self, request):
        import datetime
        from django.utils import timezone
        horizon = timezone.now().date() + datetime.timedelta(days=60)
        qs = self.get_queryset().filter(
            date_expiration_permis__lte=horizon,
            date_expiration_permis__gte=timezone.now().date()
        ).order_by('date_expiration_permis')
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def historique_conduite(self, request, pk=None):
        chauffeur = self.get_object()
        from apps.carburant.models import PleinsCarburant
        from apps.sinistres.models import Sinistre
        from django.db.models import Sum, Count

        pleins_stats = PleinsCarburant.objects.filter(chauffeur=chauffeur).aggregate(
            nb=Count('id'),
            total_litres=Sum('volume_litres'),
            total_montant=Sum('montant_fcfa')
        )
        return Response({
            'chauffeur': self.get_serializer(chauffeur).data,
            'pleins': pleins_stats,
            'nb_sinistres': Sinistre.objects.filter(chauffeur=chauffeur).count(),
        })


router = DefaultRouter()
router.register('', ChauffeurViewSet, basename='chauffeur')
urlpatterns = [path('', include(router.urls))]

"""UbiFleet — Chauffeurs Views"""

import datetime
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.permissions import RoleBasedPermission
from apps.core.agences import (
    AgenceMixin, agence_effective, agence_pour_creation, controler_agence, filtrer_par_agence,
)
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Count

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import Chauffeur, DocumentChauffeur
from .serializers import ChauffeurSerializer, DocumentChauffeurSerializer


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
        'stats': 'operateur',
        'photo': 'gestionnaire',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['agence', 'statut']
    search_fields = ['nom', 'prenom', 'matricule', 'numero_permis']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_expiration_permis']
    ordering = ['nom', 'prenom']

    def get_queryset(self):
        qs = Chauffeur.objects.select_related('agence', 'user').prefetch_related('vehicule_attitré', 'documents')
        # ?en_poste=1 : sans les chauffeurs partis (statut « Départ »)
        if self.action == 'list' and self.request.query_params.get('en_poste'):
            qs = qs.exclude(statut=Chauffeur.Statut.DEPART)
        return filtrer_par_agence(qs, self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Archivage : statut « Départ », affectations en cours terminées (le
        véhicule n'a plus ce chauffeur attitré). L'historique (prises,
        sinistres, affectations passées, documents) est conservé."""
        from apps.vehicules.models import AffectationVehicule
        chauffeur = self.get_object()
        jour = timezone.localdate()
        with transaction.atomic():
            affectations = AffectationVehicule.objects.filter(chauffeur=chauffeur)
            affectations.filter(date_debut__gt=jour).delete()
            affectations.filter(Q(date_fin__isnull=True) | Q(date_fin__gt=jour)).update(date_fin=jour)
            # Fin d'affectation aujourd'hui : le véhicule n'a plus ce chauffeur dès maintenant
            from apps.vehicules.models import Vehicule
            Vehicule.objects.filter(chauffeur_attitré=chauffeur).update(chauffeur_attitré=None)
            chauffeur.statut = Chauffeur.Statut.DEPART
            chauffeur.save(update_fields=['statut', 'updated_at'])
        return Response({'detail': f"{chauffeur.nom_complet} archivé (statut « Départ »)."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Totaux de tout l'effectif filtré (pas seulement la page affichée)."""
        qs = self.filter_queryset(self.get_queryset()).order_by()
        jour = timezone.localdate()
        par_statut = dict(qs.values_list('statut').annotate(n=Count('id')))
        actifs = qs.exclude(statut=Chauffeur.Statut.DEPART)
        return Response({
            'total': qs.count(),
            'par_statut': {code: par_statut.get(code, 0) for code, _ in Chauffeur.Statut.choices},
            'assignes': actifs.filter(vehicule_attitré__isnull=False).distinct().count(),
            'permis_expires': actifs.filter(date_expiration_permis__lt=jour).count(),
            'permis_expirant': actifs.filter(date_expiration_permis__range=(jour, jour + datetime.timedelta(days=60))).count(),
            'documents_expires': DocumentChauffeur.objects.filter(chauffeur__in=actifs, date_expiration__lt=jour).count(),
        })

    @action(detail=True, methods=['post', 'delete'], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def photo(self, request, pk=None):
        """POST (multipart, champ « photo ») : remplace la photo ; DELETE : la retire."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        chauffeur = self.get_object()
        ancienne = chauffeur.photo.name if chauffeur.photo else None
        if request.method == 'DELETE':
            chauffeur.photo = None
        else:
            fichier = request.FILES.get('photo')
            if not fichier:
                return Response({'detail': 'Aucune photo fournie.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                for v in Chauffeur._meta.get_field('photo').validators:
                    v(fichier)
            except DjangoValidationError as e:
                return Response({'detail': ' '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
            chauffeur.photo = fichier
        chauffeur.save(update_fields=['photo', 'updated_at'])
        if ancienne and ancienne != (chauffeur.photo.name if chauffeur.photo else None):
            chauffeur.photo.storage.delete(ancienne)
        return Response(self.get_serializer(chauffeur).data)

    def perform_create(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        serializer.save(created_by=user,
                        agence=agence_pour_creation(user, serializer.validated_data.get('agence')))

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

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
        # Consommation sur les véhicules conduits (12 derniers mois), vs leur référence
        import datetime
        from django.utils import timezone
        from apps.carburant.analyses import classement_chauffeurs
        prises = list(PleinsCarburant.objects.filter(
            chauffeur=chauffeur, date_plein__gte=timezone.localdate() - datetime.timedelta(days=365))
            .select_related('vehicule', 'chauffeur'))
        conso = classement_chauffeurs(prises)
        from apps.parametrage.models import TypeSinistre, libelles
        types = libelles(TypeSinistre)
        statuts = dict(Sinistre.Statut.choices)
        sinistres = [{**s, 'type_libelle': types.get(s['type_sinistre'], s['type_sinistre']),
                      'statut_libelle': statuts.get(s['statut'], s['statut'])}
                     for s in Sinistre.objects.filter(chauffeur=chauffeur).order_by('-date_sinistre').values(
                         'id', 'numero_dossier', 'type_sinistre', 'date_sinistre', 'statut', 'cout_reparation')]

        return Response({
            'chauffeur': self.get_serializer(chauffeur).data,
            'pleins': pleins_stats,
            'consommation_12_mois': conso[0] if conso else None,
            'sinistres': sinistres,
            'nb_sinistres': len(sinistres),
        })


class DocumentChauffeurViewSet(viewsets.ModelViewSet):
    """Documents des chauffeurs (?chauffeur=<id>) ; envoi en multipart (champ « fichier »)."""
    serializer_class = DocumentChauffeurSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    module   = 'chauffeurs'
    role_map = {'list': 'operateur', 'retrieve': 'operateur', 'create': 'gestionnaire',
                'update': 'gestionnaire', 'partial_update': 'gestionnaire', 'destroy': 'gestionnaire'}
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['chauffeur', 'type_document']
    pagination_class = None

    def get_permissions(self):
        return [RoleBasedPermission()]

    def get_queryset(self):
        qs = DocumentChauffeur.objects.select_related('chauffeur', 'created_by').order_by('-created_at')
        return filtrer_par_agence(qs, self.request.user, 'chauffeur__agence')

    def _controler(self, chauffeur):
        """Le chauffeur doit être visible par l'utilisateur (même agence)."""
        from rest_framework.exceptions import PermissionDenied
        if not filtrer_par_agence(Chauffeur.objects.filter(pk=chauffeur.pk), self.request.user).exists():
            raise PermissionDenied("Ce chauffeur n'est pas de votre agence.")

    def perform_create(self, serializer):
        self._controler(serializer.validated_data['chauffeur'])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        ancien = serializer.instance.fichier.name
        doc = serializer.save()
        if 'fichier' in serializer.validated_data and ancien and ancien != doc.fichier.name:
            doc.fichier.storage.delete(ancien)

    def perform_destroy(self, instance):
        nom = instance.fichier.name
        instance.delete()
        if nom:
            instance.fichier.storage.delete(nom)

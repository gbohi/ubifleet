"""UbiFleet — Contrôle Véhicule Views"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response
from apps.accounts.permissions import RoleBasedPermission
from apps.core.agences import controler_agence, filtrer_par_agence
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import ElementControle, FicheControle, PointControleDetail, PhotoControle
from .serializers import (
    ElementControleSerializer, FicheControleListSerializer,
    FicheControleDetailSerializer, FicheControleWriteSerializer,
    PointControleDetailSerializer, PhotoControleSerializer,
)


def fiches_visibles(user):
    """Fiches accessibles : celles de l'agence de l'utilisateur (toutes s'il
    n'est rattaché à aucune agence)."""
    return filtrer_par_agence(FicheControle.objects.all(), user)


def verifier_fiche_visible(user, fiche):
    if fiche is not None and not fiches_visibles(user).filter(pk=fiche.pk).exists():
        raise PermissionDenied("Cette fiche de contrôle n'appartient pas à votre agence.")


def verifier_fiche_modifiable(fiche):
    if fiche is not None and fiche.est_validee:
        raise DRFValidationError({'detail': "Fiche validée : elle n'est plus modifiable."})


STATUTS_POINT = {c for c, _ in PointControleDetail.Statut.choices}
GRAVITES = {c for c, _ in PointControleDetail.Gravite.choices}


class ElementControleViewSet(viewsets.ModelViewSet):
    """CRUD éléments de contrôle — référentiel configurable."""
    serializer_class   = ElementControleSerializer
    pagination_class   = None
    module             = 'controle'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'responsable_flotte',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'responsable_flotte',
    }

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
    module             = 'controle'
    permission_classes = [RoleBasedPermission]
    permission_actions = {'valider': 'valider_fiche'}
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'operateur',
        'update': 'operateur',
        'partial_update': 'operateur',
        'destroy': 'responsable_flotte',
        'valider': 'operateur',
        'rapport': 'operateur',
        'stats': 'operateur',
        'bulk_save': 'operateur',
    }
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
        qs = fiches_visibles(self.request.user).select_related(
            'vehicule', 'chauffeur', 'agence', 'created_by', 'validee_par'
        ).annotate(
            nb_points_a=Count('points', distinct=True),
            nb_nc_a=Count('points', filter=Q(points__statut='non_conforme'), distinct=True),
            nb_photos_a=Count('photos', distinct=True),
        )

        # Filtres additionnels
        date_debut = self.request.query_params.get('date_debut')
        date_fin   = self.request.query_params.get('date_fin')
        immat      = self.request.query_params.get('immatriculation')
        if date_debut: qs = qs.filter(date_heure__date__gte=date_debut)
        if date_fin:   qs = qs.filter(date_heure__date__lte=date_fin)
        if immat:      qs = qs.filter(vehicule__immatriculation__icontains=immat)
        a_valider  = self.request.query_params.get('a_valider')
        if a_valider == 'true': qs = qs.filter(validee_le__isnull=True)
        return qs

    def perform_create(self, serializer):
        """L'agence de la fiche est celle du véhicule contrôlé."""
        user = self.request.user
        vehicule = serializer.validated_data['vehicule']
        controler_agence(user, {'agence': vehicule.agence})
        serializer.save(created_by=user, agence=vehicule.agence,
                        statut_global=FicheControle.StatutGlobal.EN_COURS)

    def perform_update(self, serializer):
        vehicule = serializer.validated_data.get('vehicule')
        if vehicule is not None:
            controler_agence(self.request.user, {'agence': vehicule.agence})
            serializer.save(agence=vehicule.agence)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        for photo in instance.photos.all():
            photo.image.delete(save=False)
        instance.delete()

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide la fiche : tous les points obligatoires doivent être
        renseignés, chaque non-conformité doit avoir une gravité. Le statut
        global est calculé et la fiche est figée. Une non-conformité majeure
        ou bloquante crée une alerte pour l'agence."""
        fiche = self.get_object()
        verifier_fiche_modifiable(fiche)
        renseignes = set(fiche.points.values_list('element_id', flat=True))
        manquants = list(ElementControle.objects.filter(actif=True, obligatoire=True)
                         .exclude(id__in=renseignes).values_list('nom', flat=True))
        if manquants:
            return Response({'detail': "Points obligatoires non renseignés : " + ', '.join(manquants) + '.'},
                            status=400)
        if not renseignes:
            return Response({'detail': "Aucun point contrôlé : renseignez la fiche avant de la valider."},
                            status=400)
        if fiche.points.filter(statut='non_conforme', gravite__isnull=True).exists():
            return Response({'detail': "Indiquez la gravité de chaque point non conforme."}, status=400)
        with transaction.atomic():
            fiche.statut_global = fiche.calculer_statut_global()
            fiche.validee_le = timezone.now()
            fiche.validee_par = request.user
            fiche.save()
            self._alerter_non_conformites(fiche)
        return Response({'statut_global': fiche.statut_global,
                         'statut_display': fiche.get_statut_global_display()})

    @staticmethod
    def _alerter_non_conformites(fiche):
        from apps.alertes.models import Alerte
        graves = list(fiche.points.filter(statut='non_conforme', gravite__in=['majeur', 'bloquant'])
                      .select_related('element').order_by('element__categorie', 'element__nom'))
        if not graves:
            return
        bloquant = any(p.gravite == 'bloquant' for p in graves)
        v = fiche.vehicule
        Alerte.objects.create(
            type_alerte=Alerte.TypeAlerte.CONTROLE_NON_CONFORME,
            priorite=Alerte.Priorite.CRITIQUE if bloquant else Alerte.Priorite.HAUTE,
            titre=f"Contrôle non conforme — {v.immatriculation}",
            message=(f"{fiche.get_type_controle_display()} du {timezone.localtime(fiche.date_heure):%d/%m/%Y %H:%M} : "
                     + '; '.join(f"{p.element.nom} ({p.get_gravite_display().lower()})"
                                 + (f" — {p.remarque}" if p.remarque else '') for p in graves)
                     + ('. Véhicule à immobiliser jusqu\'à réparation.' if bloquant else '.')),
            vehicule=v, chauffeur=fiche.chauffeur, agence=fiche.agence,
        )

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
            'partiels':     qs.filter(statut_global='partiel').count(),
            'en_cours':     qs.filter(validee_le__isnull=True).count(),
            'par_type':     list(qs.values('type_controle')
                                    .annotate(nb=Count('id')).order_by('-nb')),
        })


class PointControleDetailViewSet(viewsets.ModelViewSet):
    """CRUD points de contrôle d'une fiche."""
    serializer_class   = PointControleDetailSerializer
    pagination_class   = None
    module             = 'controle'
    permission_classes = [RoleBasedPermission]
    permission_actions = {'valider': 'valider_fiche'}
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'operateur',
        'update': 'operateur',
        'partial_update': 'operateur',
        'destroy': 'responsable_flotte',
        'valider': 'operateur',
        'rapport': 'operateur',
        'stats': 'operateur',
        'bulk_save': 'operateur',
    }

    def get_queryset(self):
        qs = PointControleDetail.objects.select_related('element', 'fiche').filter(
            fiche__in=fiches_visibles(self.request.user)
        )
        fiche_id = self.request.query_params.get('fiche')
        if fiche_id:
            qs = qs.filter(fiche__id=fiche_id)
        return qs

    def perform_create(self, serializer):
        fiche = serializer.validated_data.get('fiche')
        verifier_fiche_visible(self.request.user, fiche)
        verifier_fiche_modifiable(fiche)
        serializer.save()

    def perform_update(self, serializer):
        verifier_fiche_modifiable(serializer.instance.fiche)
        serializer.save()

    def perform_destroy(self, instance):
        verifier_fiche_modifiable(instance.fiche)
        instance.delete()

    @action(detail=False, methods=['post'])
    def bulk_save(self, request):
        """Sauvegarde plusieurs points en une seule requête."""
        fiche_id = request.data.get('fiche_id')
        points   = request.data.get('points', [])
        if not fiche_id:
            return Response({'detail': 'fiche_id requis.'}, status=400)
        try:
            fiche = fiches_visibles(request.user).get(id=fiche_id)
        except (FicheControle.DoesNotExist, ValueError, ValidationError):
            return Response({'detail': 'Fiche introuvable.'}, status=404)

        verifier_fiche_modifiable(fiche)
        if not isinstance(points, list):
            return Response({'detail': 'points doit être une liste.'}, status=400)

        elements = {e.id: e for e in ElementControle.objects.filter(
            id__in=[p.get('element') for p in points if isinstance(p, dict)])}
        erreurs = []
        for p in points:
            e = elements.get(p.get('element')) if isinstance(p, dict) else None
            if e is None:
                erreurs.append(f"Point inconnu : {p.get('element') if isinstance(p, dict) else p}.")
                continue
            statut = p.get('statut', 'conforme')
            if statut not in STATUTS_POINT:
                erreurs.append(f"{e.nom} : statut invalide.")
            elif statut == 'non_conforme' and p.get('gravite') not in GRAVITES:
                erreurs.append(f"{e.nom} : indiquez la gravité de la non-conformité.")
        if erreurs:
            return Response({'detail': ' '.join(erreurs)}, status=400)

        with transaction.atomic():
            for p in points:
                statut = p.get('statut', 'conforme')
                PointControleDetail.objects.update_or_create(
                    fiche=fiche, element_id=p['element'],
                    defaults={'statut': statut,
                              'gravite': p.get('gravite') if statut == 'non_conforme' else None,
                              'remarque': (p.get('remarque') or '').strip()},
                )
        return Response({'saved': len(points), 'statut_global': fiche.statut_global})


class PhotoControleViewSet(viewsets.ModelViewSet):
    """Upload / suppression des photos d'une fiche."""
    serializer_class   = PhotoControleSerializer
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    pagination_class   = None
    module             = 'controle'
    permission_classes = [RoleBasedPermission]
    permission_actions = {'valider': 'valider_fiche'}
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'operateur',
        'update': 'operateur',
        'partial_update': 'operateur',
        'destroy': 'responsable_flotte',
        'valider': 'operateur',
        'rapport': 'operateur',
        'stats': 'operateur',
        'bulk_save': 'operateur',
    }

    def get_queryset(self):
        qs = PhotoControle.objects.filter(fiche__in=fiches_visibles(self.request.user))
        fiche_id = self.request.query_params.get('fiche')
        if fiche_id:
            qs = qs.filter(fiche__id=fiche_id)
        return qs

    def perform_create(self, serializer):
        fiche = serializer.validated_data.get('fiche')
        verifier_fiche_visible(self.request.user, fiche)
        verifier_fiche_modifiable(fiche)
        serializer.save()

    def perform_destroy(self, instance):
        verifier_fiche_modifiable(instance.fiche)
        instance.image.delete(save=False)
        instance.delete()

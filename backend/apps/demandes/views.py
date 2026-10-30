"""UbiFleet — Demandes & Workflow Views"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.db.models import Count, Q

from .models import (
    TypeDemande, NiveauValidation, Demande,
    ValidationDemande, LigneDemandeAchat,
)
from .serializers import (
    TypeDemandeSerializer, NiveauValidationSerializer,
    LigneDemandeAchatSerializer,
    DemandeListSerializer, DemandeDetailSerializer, DemandeWriteSerializer,
)
from apps.accounts.permissions import IsSuperAdmin, RoleBasedPermission
from . import workflow
from .signals import demande_cloturee
from apps.core.agences import (
    agence_pour_creation, controler_agence, filtrer_par_agence, voit_toutes_agences,
)


# ── Règles d'accès aux demandes ───────────────────────────────────────

def demandes_visibles(user):
    """Demandes consultables : celles de son agence (toutes sans agence de
    rattachement), plus ses propres demandes et celles qu'il a traitées."""
    qs = Demande.objects.all()
    if voit_toutes_agences(user):
        return qs
    return qs.filter(
        Q(agence_id=user.agence_id) | Q(demandeur=user) | Q(validations__validateur=user)
    ).distinct()


def verifier_modifiable(user, demande):
    """Seul le demandeur (ou le super admin) modifie une demande, et
    uniquement tant qu'elle est en brouillon."""
    if demande.demandeur_id != user.id and not user.is_super_admin:
        raise PermissionDenied("Seul le demandeur peut modifier cette demande.")
    if demande.statut != Demande.Statut.BROUILLON:
        raise ValidationError(
            {'detail': 'Seule une demande en brouillon peut être modifiée.'}
        )


def verifier_validateur(user, demande, verbe):
    """Contrôle du droit de valider / rejeter le niveau actuel de la demande."""
    if user.is_super_admin:
        return None
    if demande.demandeur_id == user.id:
        return Response(
            {'detail': f'Vous ne pouvez pas {verbe} votre propre demande.'},
            status=status.HTTP_403_FORBIDDEN
        )
    niveau_requis = NiveauValidation.objects.filter(
        type_demande=demande.type_demande, niveau=demande.niveau_actuel
    ).select_related('role_min').first()
    if niveau_requis is None:
        return Response(
            {'detail': 'Aucun niveau de validation configuré pour ce type de demande.'},
            status=status.HTTP_403_FORBIDDEN
        )
    # Un niveau sans rôle requis n'est validable que par le super admin
    # (auparavant : par n'importe quel utilisateur).
    if niveau_requis.role_min_id is None:
        return Response(
            {'detail': f"Aucun rôle validateur n'est défini pour le niveau "
                       f"« {niveau_requis.libelle} ». Contactez l'administrateur."},
            status=status.HTTP_403_FORBIDDEN
        )
    if niveau_requis.role_min_id != user.role_id:
        return Response(
            {'detail': f"Vous n'avez pas le rôle requis pour {verbe} ce niveau "
                       f"({niveau_requis.libelle} — rôle requis : "
                       f"{niveau_requis.role_min.nom})."},
            status=status.HTTP_403_FORBIDDEN
        )
    return None


class ConfigWorkflowPermissionMixin:
    """Types de demande et niveaux de validation : lecture pour tous
    (formulaire de demande), configuration réservée au super admin."""

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


# ── Types de demande ──────────────────────────────────────────────────

def _creer_alerte_demande(demande, niveau_actuel):
    """Crée une alerte pour les utilisateurs ayant le rôle requis au niveau actuel."""
    try:
        from apps.alertes.models import Alerte
        from apps.demandes.models import NiveauValidation
        from apps.accounts.models import User

        # Trouver le niveau de validation configuré
        try:
            nv = NiveauValidation.objects.select_related('role_min').get(
                type_demande=demande.type_demande,
                niveau=niveau_actuel
            )
        except NiveauValidation.DoesNotExist:
            return

        # Trouver les utilisateurs destinataires
        if nv.role_min:
            validateurs = list(User.objects.filter(role=nv.role_min, is_active=True))
        else:
            validateurs = list(User.objects.filter(is_active=True, role__niveau__gte=6))

        if not validateurs:
            return

        titre   = f"Demande à valider — {demande.numero}"
        message = (
            f"La demande « {demande.titre} » ({demande.type_demande.nom}) "
            f"de {demande.demandeur.get_full_name() or demande.demandeur.username} "
            f"attend votre validation (Niveau {niveau_actuel} — {nv.libelle})."
        )

        for validateur in validateurs:
            # Chercher une alerte active existante pour ce validateur et cette demande
            alerte_existante = Alerte.objects.filter(
                type_alerte  = 'demande_a_valider',
                destinataire = validateur,
                statut__in   = [Alerte.Statut.ACTIVE, Alerte.Statut.LUE],
                message__contains = demande.numero,
            ).first()

            if alerte_existante:
                alerte_existante.titre   = titre
                alerte_existante.message = message
                alerte_existante.statut  = Alerte.Statut.ACTIVE
                alerte_existante.save()
            else:
                Alerte.objects.create(
                    type_alerte  = 'demande_a_valider',
                    destinataire = validateur,
                    titre        = titre,
                    message      = message,
                    priorite     = Alerte.Priorite.HAUTE,
                    agence       = demande.agence,
                    statut       = Alerte.Statut.ACTIVE,
                )

    except Exception as e:
        # Logger l'erreur sans bloquer le workflow
        import logging
        logging.getLogger(__name__).warning(f"Erreur création alerte demande: {e}")


def _notifier_demandeur(demande, message, priorite='normale'):
    """Crée une alerte pour le demandeur pour l'informer de l'avancement."""
    try:
        from apps.alertes.models import Alerte
        from apps.accounts.models import User

        # Récupérer l'objet User correspondant au demandeur
        try:
            destinataire = User.objects.get(pk=demande.demandeur.pk)
        except User.DoesNotExist:
            return

        Alerte.objects.create(
            type_alerte  = 'demande_a_valider',
            destinataire = destinataire,
            titre        = f"Demande {demande.numero} — {message}",
            message      = (
                f"Votre demande « {demande.titre} » ({demande.type_demande.nom}) "
                f"a été {message.lower()}."
            ),
            priorite = priorite,
            agence   = demande.agence,
            statut   = 'active',
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Erreur notification demandeur: {e}")


def _supprimer_alerte_niveau(demande, niveau):
    """Marque comme traitées les alertes des validateurs du niveau donné."""
    try:
        from apps.alertes.models import Alerte
        from apps.demandes.models import NiveauValidation
        from apps.accounts.models import User
        try:
            nv = NiveauValidation.objects.select_related('role_min').get(
                type_demande=demande.type_demande, niveau=niveau
            )
        except NiveauValidation.DoesNotExist:
            return
        if nv.role_min:
            validateurs = list(User.objects.filter(role=nv.role_min, is_active=True))
        else:
            validateurs = list(User.objects.filter(is_active=True, role__niveau__gte=6))
        Alerte.objects.filter(
            type_alerte='demande_a_valider',
            destinataire__in=validateurs,
            message__contains=demande.numero,
        ).update(statut='traitee')
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Erreur suppression alerte niveau: {e}")


def _supprimer_alerte_demande(demande):
    """Marque comme traitées toutes les alertes liées à cette demande."""
    try:
        from apps.alertes.models import Alerte
        Alerte.objects.filter(
            type_alerte='demande_a_valider',
            message__contains=demande.numero,
        ).update(statut=Alerte.Statut.TRAITEE)
    except Exception:
        pass


class TypeDemandeViewSet(ConfigWorkflowPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = TypeDemandeSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = TypeDemande.objects.prefetch_related('niveaux__role_min')
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


# ── Niveaux de validation ─────────────────────────────────────────────
class NiveauValidationViewSet(ConfigWorkflowPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = NiveauValidationSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = NiveauValidation.objects.select_related('type_demande', 'role_min')
        type_id = self.request.query_params.get('type_demande')
        if type_id:
            qs = qs.filter(type_demande__id=type_id)
        return qs


# ── Lignes d'achat ────────────────────────────────────────────────────
class LigneDemandeAchatViewSet(viewsets.ModelViewSet):
    serializer_class   = LigneDemandeAchatSerializer
    pagination_class   = None
    module             = 'demandes'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'chauffeur',
        'retrieve': 'chauffeur',
        'create': 'chauffeur',
        'update': 'chauffeur',
        'partial_update': 'chauffeur',
        'destroy': 'chauffeur',
        'bulk_save': 'chauffeur',
    }

    def get_queryset(self):
        qs = LigneDemandeAchat.objects.filter(
            demande__in=demandes_visibles(self.request.user)
        )
        demande_id = self.request.query_params.get('demande')
        if demande_id:
            qs = qs.filter(demande__id=demande_id)
        return qs

    def perform_create(self, serializer):
        verifier_modifiable(self.request.user, serializer.validated_data['demande'])
        serializer.save()

    def perform_update(self, serializer):
        verifier_modifiable(self.request.user, serializer.instance.demande)
        if 'demande' in serializer.validated_data:
            verifier_modifiable(self.request.user, serializer.validated_data['demande'])
        serializer.save()

    def perform_destroy(self, instance):
        verifier_modifiable(self.request.user, instance.demande)
        instance.delete()

    @action(detail=False, methods=['post'])
    def bulk_save(self, request):
        """Remplace toutes les lignes d'une demande."""
        demande_id = request.data.get('demande_id')
        lignes     = request.data.get('lignes', [])
        if not demande_id:
            return Response({'detail': 'demande_id requis.'}, status=400)
        try:
            demande = demandes_visibles(request.user).get(id=demande_id)
        except (Demande.DoesNotExist, ValueError, DjangoValidationError):
            return Response({'detail': 'Demande introuvable.'}, status=404)
        verifier_modifiable(request.user, demande)

        LigneDemandeAchat.objects.filter(demande=demande).delete()
        created = []
        for i, l in enumerate(lignes):
            if not str(l.get('designation', '')).strip():
                continue
            obj = LigneDemandeAchat.objects.create(
                demande       = demande,
                designation   = str(l.get('designation', '')).strip(),
                quantite      = l.get('quantite', 1),
                unite         = l.get('unite', ''),
                prix_unitaire = l.get('prix_unitaire') or None,
                fournisseur   = l.get('fournisseur', ''),
                notes         = l.get('notes', ''),
                ordre         = i,
            )
            created.append(obj.id)

        # Recalculer montant_estime
        total = sum(
            float(o.quantite) * float(o.prix_unitaire)
            for o in LigneDemandeAchat.objects.filter(demande=demande)
            if o.prix_unitaire
        )
        if total:
            demande.montant_estime = total
            demande.save()

        return Response({'saved': len(created)})


# ── Demandes ──────────────────────────────────────────────────────────
class DemandeViewSet(viewsets.ModelViewSet):
    module             = 'demandes'
    permission_classes = [RoleBasedPermission]
    permission_actions = {'valider': 'valider_demande'}
    # Tout utilisateur peut créer et suivre ses demandes ; les règles fines
    # (propriétaire, brouillon, rôle validateur) sont vérifiées par objet.
    role_map = {
        'list': 'chauffeur',
        'retrieve': 'chauffeur',
        'create': 'chauffeur',
        'update': 'chauffeur',
        'partial_update': 'chauffeur',
        'destroy': 'chauffeur',
        'soumettre': 'chauffeur',
        'valider': 'chauffeur',
        'rejeter': 'chauffeur',
        'annuler': 'chauffeur',
        'stats': 'chauffeur',
        'a_valider': 'chauffeur',
    }
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields   = ['statut', 'priorite', 'type_demande', 'agence', 'demandeur']
    search_fields      = ['numero', 'titre', 'description']
    ordering_fields    = ['created_at', 'date_souhaitee', 'priorite']
    ordering           = ['-created_at']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DemandeWriteSerializer
        if self.action == 'retrieve':
            return DemandeDetailSerializer
        return DemandeListSerializer

    def get_queryset(self):
        user = self.request.user

        # Pour les actions sur un objet spécifique (retrieve, update, valider, rejeter...)
        # on ne filtre PAS par vue : toutes les demandes visibles par l'utilisateur
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy',
                            'valider', 'rejeter', 'soumettre', 'annuler']:
            return demandes_visibles(user).select_related(
                'type_demande', 'demandeur', 'agence', 'vehicule', 'chauffeur'
            ).prefetch_related('validations__validateur', 'lignes_achat')

        qs = Demande.objects.select_related(
            'type_demande', 'demandeur', 'agence', 'vehicule', 'chauffeur'
        ).prefetch_related('validations__validateur', 'lignes_achat')

        vue = self.request.query_params.get('vue', 'mes_demandes')
        if vue == 'mes_demandes':
            qs = qs.filter(demandeur=user)
        elif vue == 'validees_par_moi':
            qs = qs.filter(validations__validateur=user,
                           validations__decision='approuve').distinct()
        elif vue == 'agence' and getattr(user, 'agence', None):
            qs = qs.filter(agence=user.agence)
        elif vue == 'toutes':
            qs = filtrer_par_agence(qs, user)
        else:
            qs = qs.filter(demandeur=user)

        date_debut = self.request.query_params.get('date_debut')
        date_fin   = self.request.query_params.get('date_fin')
        if date_debut:
            qs = qs.filter(created_at__date__gte=date_debut)
        if date_fin:
            qs = qs.filter(created_at__date__lte=date_fin)

        return qs

    def perform_create(self, serializer):
        user   = self.request.user
        controler_agence(user, serializer.validated_data)
        agence = agence_pour_creation(user, serializer.validated_data.get('agence'))
        serializer.save(demandeur=user, created_by=user, agence=agence)

    def perform_update(self, serializer):
        verifier_modifiable(self.request.user, serializer.instance)
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    def perform_destroy(self, instance):
        verifier_modifiable(self.request.user, instance)
        instance.delete()

    # ── Workflow ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        demande = self.get_object()
        if demande.demandeur_id != request.user.id and not request.user.is_super_admin:
            raise PermissionDenied("Seul le demandeur peut soumettre cette demande.")
        if demande.statut != Demande.Statut.BROUILLON:
            return Response(
                {'detail': 'Seule une demande en brouillon peut être soumise.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        workflow.soumettre(demande)
        return Response(DemandeDetailSerializer(demande).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def valider(self, request, pk=None):
        # Verrou de ligne : évite une double validation simultanée du même niveau
        demande     = Demande.objects.select_for_update().get(pk=self.get_object().pk)
        commentaire = request.data.get('commentaire', '')

        if demande.statut not in [Demande.Statut.SOUMISE, Demande.Statut.EN_VALIDATION]:
            return Response(
                {'detail': 'Cette demande ne peut pas être validée.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        refus = verifier_validateur(request.user, demande, 'valider')
        if refus:
            return refus

        val, _ = ValidationDemande.objects.get_or_create(
            demande=demande, niveau=demande.niveau_actuel
        )
        val.decision      = ValidationDemande.Decision.APPROUVE
        val.validateur    = request.user
        val.commentaire   = commentaire
        val.date_decision = timezone.now()
        val.save()

        if demande.niveau_actuel >= demande.type_demande.nb_niveaux:
            demande.statut          = Demande.Statut.APPROUVEE
            demande.date_traitement = timezone.now()
            _supprimer_alerte_niveau(demande, demande.niveau_actuel)
            # Notifier le demandeur : approbation finale
            _notifier_demandeur(demande, 'approuvée définitivement', priorite='haute')
            demande.save()
            demande_cloturee.send(sender=Demande, demande=demande, decision='approuvee',
                                  utilisateur=request.user)
        else:
            _supprimer_alerte_niveau(demande, demande.niveau_actuel)
            niveau_valide = demande.niveau_actuel
            demande.niveau_actuel += 1
            demande.statut         = Demande.Statut.EN_VALIDATION
            ValidationDemande.objects.get_or_create(
                demande=demande, niveau=demande.niveau_actuel,
                defaults={'decision': ValidationDemande.Decision.EN_ATTENTE}
            )
            # Notifier le demandeur : validation intermédiaire
            _notifier_demandeur(
                demande,
                f'validée au niveau {niveau_valide} — en attente du niveau {demande.niveau_actuel}',
                priorite='normale'
            )
            # Notifier les validateurs du niveau suivant
            _creer_alerte_demande(demande, demande.niveau_actuel)

        demande.save()
        return Response(DemandeDetailSerializer(demande).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def rejeter(self, request, pk=None):
        demande     = Demande.objects.select_for_update().get(pk=self.get_object().pk)
        commentaire = request.data.get('commentaire', '')
        if not commentaire:
            return Response(
                {'detail': 'Un motif de rejet est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if demande.statut not in [Demande.Statut.SOUMISE, Demande.Statut.EN_VALIDATION]:
            return Response(
                {'detail': 'Cette demande ne peut pas être rejetée.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        refus = verifier_validateur(request.user, demande, 'rejeter')
        if refus:
            return refus
        val, _ = ValidationDemande.objects.get_or_create(
            demande=demande, niveau=demande.niveau_actuel
        )
        val.decision      = ValidationDemande.Decision.REJETE
        val.validateur    = request.user
        val.commentaire   = commentaire
        val.date_decision = timezone.now()
        val.save()

        demande.statut          = Demande.Statut.REJETEE
        demande.date_traitement = timezone.now()
        demande.save()
        demande_cloturee.send(sender=Demande, demande=demande, decision='rejetee',
                              utilisateur=request.user)
        # Supprimer les alertes des validateurs et notifier le demandeur
        _supprimer_alerte_demande(demande)
        _notifier_demandeur(demande, f'rejetée — Motif : {commentaire}', priorite='haute')
        return Response(DemandeDetailSerializer(demande).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        demande = self.get_object()
        if not demande.peut_etre_annulee():
            return Response(
                {'detail': 'Cette demande ne peut plus être annulée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if demande.demandeur != request.user and not request.user.is_admin_level():
            return Response(
                {'detail': 'Seul le demandeur peut annuler.'},
                status=status.HTTP_403_FORBIDDEN
            )
        with transaction.atomic():
            demande.statut = Demande.Statut.ANNULEE
            demande.save()
            demande_cloturee.send(sender=Demande, demande=demande, decision='annulee',
                                  utilisateur=request.user)
        return Response({'detail': 'Demande annulée.'})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            'total':      qs.count(),
            'brouillons': qs.filter(statut='brouillon').count(),
            'en_attente': qs.filter(statut__in=['soumise', 'en_validation']).count(),
            'approuvees': qs.filter(statut='approuvee').count(),
            'rejetees':   qs.filter(statut='rejetee').count(),
            'par_type':   list(qs.values('type_demande__nom')
                               .annotate(nb=Count('id')).order_by('-nb')),
            'par_priorite': list(qs.values('priorite').annotate(nb=Count('id'))),
        })

    @action(detail=False, methods=['get'])
    def a_valider(self, request):
        """Demandes visibles uniquement par le rôle requis au niveau actuel."""
        user      = request.user
        user_role = getattr(user, 'role', None)

        # Le super admin voit toutes les demandes en attente (de son agence
        # s'il est rattaché à une agence)
        if user.is_super_admin:
            qs = filtrer_par_agence(Demande.objects.filter(
                statut__in=['soumise', 'en_validation']
            ), user).select_related('type_demande', 'demandeur', 'agence')
            return Response(DemandeListSerializer(qs, many=True).data)

        if not user_role:
            return Response([])

        # Récupérer les (type_demande_id, niveau) où ce rôle est requis exactement
        niveaux = list(NiveauValidation.objects.filter(
            role_min=user_role
        ).values_list('type_demande_id', 'niveau'))

        if not niveaux:
            return Response([])

        # Filtrer les demandes dont le niveau actuel correspond exactement
        filtre = Q()
        for type_id, niveau in niveaux:
            filtre |= Q(type_demande_id=type_id, niveau_actuel=niveau)

        qs = filtrer_par_agence(Demande.objects.filter(
            statut__in=['soumise', 'en_validation']
        ), user).filter(filtre).exclude(demandeur=user).select_related(
            'type_demande', 'demandeur', 'agence'
        ).distinct()

        return Response(DemandeListSerializer(qs, many=True).data)

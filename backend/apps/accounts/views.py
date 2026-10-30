"""UbiFleet — Accounts Views"""

from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.module_loading import import_string
from apps.core.referentiels import SuppressionProtegeeMixin
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, Agence, Role, PermissionRole
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    AgenceSerializer, ChangePasswordSerializer, RoleSerializer,
    UbiFleetTokenObtainSerializer, ResetProfileSerializer,
    PermissionRoleSerializer,
)
from .permissions import (
    IsSuperAdmin, IsAdminOrReadOnly, CanManageUsers, IsFleetManager, can_manage_user,
)
from apps.core.agences import (
    MESSAGE_AUTRE_AGENCE, agence_pour_creation, controler_agence,
    filtrer_par_agence, voit_toutes_agences,
)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class   = UbiFleetTokenObtainSerializer


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            return Response({'detail': 'Déconnexion réussie.'})
        except Exception:
            return Response({'detail': 'Token invalide.'}, status=400)


class MeView(generics.RetrieveAPIView):
    """Lecture seule : la mise à jour du profil passe par /me/profile/,
    qui n'expose ni le rôle ni le statut actif (anti auto-promotion)."""
    serializer_class   = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class   = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.get_object()
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Mot de passe modifié avec succès.'})


class ResetProfileView(generics.UpdateAPIView):
    serializer_class   = ResetProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'detail': 'Profil mis à jour.',
            'user': UserSerializer(instance).data
        })


class RoleViewSet(viewsets.ModelViewSet):
    """CRUD des rôles — niveau 8 (DG) minimum pour modifier."""
    queryset           = Role.objects.annotate_nb_users() if hasattr(Role.objects, 'annotate_nb_users') else Role.objects.all()
    module   = 'roles'
    serializer_class   = RoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['nom', 'code', 'description']
    ordering_fields    = ['niveau', 'nom', 'created_at']

    def get_queryset(self):
        return Role.objects.all().order_by('-niveau', 'nom')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response(
                {'detail': "Ce rôle système ne peut pas être supprimé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if role.utilisateurs.exists():
            return Response(
                {'detail': f"Ce rôle est attribué à {role.utilisateurs.count()} utilisateur(s). "
                           "Réaffectez-les avant de supprimer ce rôle."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('agence', 'role').order_by('-date_joined')

    def get_queryset(self):
        # Un gestionnaire rattaché à une agence ne voit que ses utilisateurs
        return filtrer_par_agence(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(agence=agence_pour_creation(user, serializer.validated_data.get('agence')))

    def perform_update(self, serializer):
        user = self.request.user
        # Rattaché à une agence : impossible de passer un compte en
        # « Toutes les agences » (agence vide) ou dans une autre agence.
        if not voit_toutes_agences(user) and 'agence' in serializer.validated_data \
                and serializer.validated_data['agence'] is None:
            raise PermissionDenied(MESSAGE_AUTRE_AGENCE)
        controler_agence(user, serializer.validated_data)
        serializer.save()
    module   = 'users'
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'agence', 'is_active']
    search_fields    = ['email', 'first_name', 'last_name', 'username']
    ordering_fields  = ['date_joined', 'last_name']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsSuperAdmin()]
        return [CanManageUsers()]

    def get_object(self):
        """Interdit de modifier un compte de niveau égal ou supérieur au sien
        (hors super admin), pour empêcher toute prise de contrôle."""
        user = super().get_object()
        if self.action not in ('retrieve',) and not can_manage_user(self.request.user, user):
            raise PermissionDenied(
                "Vous ne pouvez pas agir sur un compte de niveau égal ou supérieur au vôtre."
            )
        return user

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response({'detail': 'Vous ne pouvez pas vous désactiver vous-même.'}, status=400)
        user.is_active = not user.is_active
        user.save()
        return Response({'detail': f"Utilisateur {'activé' if user.is_active else 'désactivé'}.", 'is_active': user.is_active})

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        pwd  = request.data.get('new_password')
        if not pwd or len(pwd) < 8:
            return Response({'detail': 'Mot de passe trop court (min. 8 caractères).'}, status=400)
        user.set_password(pwd)
        user.save()
        return Response({'detail': 'Mot de passe réinitialisé.'})


class AgenceViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    """Lecture pour tous (listes déroulantes). Un utilisateur rattaché à une
    agence ne voit et ne peut modifier que la sienne, et ne peut pas en créer."""
    module             = 'agences'
    queryset           = Agence.objects.filter(is_active=True)
    serializer_class   = AgenceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['nom', 'code', 'ville']
    relations_utilisation = [('vehicules', 'véhicule(s)'), ('utilisateurs', 'utilisateur(s)')]

    def get_queryset(self):
        # Rattaché à une agence : seule la sienne apparaît (listes, filtres)
        return filtrer_par_agence(super().get_queryset(), self.request.user, 'pk')

    def _verifier_modifiable(self, agence=None):
        user = self.request.user
        if voit_toutes_agences(user):
            return
        if agence is None or agence.pk != user.agence_id:
            raise PermissionDenied(MESSAGE_AUTRE_AGENCE)

    def perform_create(self, serializer):
        self._verifier_modifiable()
        serializer.save()

    def perform_update(self, serializer):
        self._verifier_modifiable(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._verifier_modifiable(instance)
        instance.delete()


class PermissionRoleViewSet(viewsets.ModelViewSet):
    """CRUD des permissions — super_admin uniquement."""
    queryset           = PermissionRole.objects.select_related('role').all().order_by('role__niveau', 'module', 'action')
    module   = 'permissions'
    serializer_class   = PermissionRoleSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields   = ['role', 'module', 'action', 'autorise']

    def perform_create(self, serializer):
        from apps.accounts.permission_cache import invalidate
        serializer.save(); invalidate()

    def perform_update(self, serializer):
        from apps.accounts.permission_cache import invalidate
        serializer.save(); invalidate()

    def perform_destroy(self, instance):
        from apps.accounts.permission_cache import invalidate
        instance.delete(); invalidate()


class PermissionMetaView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = Role.objects.filter(is_active=True).order_by('-niveau')
        actions_map = dict(PermissionRole.ACTIONS)
        return Response({
            'roles':   RoleSerializer(roles, many=True).data,
            'modules': [{'value': v, 'label': l} for v, l in PermissionRole.MODULES],
            'actions': [{'value': v, 'label': l} for v, l in PermissionRole.ACTIONS],
            # Actions spécifiques par module
            'module_actions': {
                module: [
                    {'value': a, 'label': actions_map.get(a, a)}
                    for a in actions
                ]
                for module, actions in PermissionRole.MODULE_ACTIONS.items()
            },
        })


class PermissionBulkView(generics.GenericAPIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        from apps.accounts.permission_cache import invalidate
        items   = request.data if isinstance(request.data, list) else []
        updated = 0
        for item in items:
            role_id = item.get('role')
            try:
                role = Role.objects.get(pk=role_id)
            except Role.DoesNotExist:
                continue
            PermissionRole.objects.update_or_create(
                role=role, module=item['module'], action=item['action'],
                defaults={'autorise': item['autorise']}
            )
            updated += 1
        invalidate()
        return Response({'detail': f'{updated} permission(s) mises à jour.'})


# Écrans de l'interface → (vue API qui les alimente, action). Le droit
# d'accès est évalué avec les permissions réelles de la vue (y compris les
# règles PermissionRole en base), pour que le menu reflète exactement ce que
# l'API autorise.
ACCES_ECRANS = {
    'dashboard':             ('apps.rapports.views.DashboardDGView', None),
    'vehicules':             ('apps.vehicules.views.VehiculeViewSet', 'list'),
    'releves_km':            ('apps.vehicules.views.ReleveKilometrageViewSet', 'list'),
    'carburant':             ('apps.carburant.views.PleinViewSet', 'list'),
    'restitution_mensuelle': ('apps.vehicules.views.ConsommationKmView', 'list'),
    'transactions_total':    ('apps.total_import.views.TransactionCarburantViewSet', 'list'),
    'entretien':             ('apps.entretien.views.InterventionViewSet', 'list'),
    'etat_parc':             ('apps.vehicules.views.VehiculeViewSet', 'etat_parc'),
    'sinistres':             ('apps.sinistres.views.SinistreViewSet', 'list'),
    'budget':                ('apps.budget.views.BudgetViewSet', 'list'),
    'grand_livre':           ('apps.grand_livre.views.LigneGrandLivreViewSet', 'list'),
    'chauffeurs':            ('apps.chauffeurs.views.ChauffeurViewSet', 'list'),
    'demandes':              ('apps.demandes.views.DemandeViewSet', 'list'),
    'controle':              ('apps.controle.views.FicheControleViewSet', 'list'),
    'rapports':              ('apps.rapports.views.RapportCarburantView', None),
    'alertes':               ('apps.alertes.views.AlerteViewSet', 'list'),
    'alertes_generer':       ('apps.alertes.views.AlerteViewSet', 'generer'),
    'utilisateurs':          ('apps.accounts.views.UserViewSet', 'list'),
    'roles':                 ('apps.accounts.views.RoleViewSet', 'create'),
    'permissions':           ('apps.accounts.views.PermissionRoleViewSet', 'list'),
    'parametres':            ('apps.parametrage.views.ParametreViewSet', 'bulk_update'),
    # Droits d'écriture affinés dans la page Paramètres
    'referentiels_ecriture': ('apps.parametrage.views.MarqueVehiculeViewSet', 'create'),
    'circuits_ecriture':     ('apps.demandes.views.TypeDemandeViewSet', 'create'),
    'elements_controle_ecriture': ('apps.controle.views.ElementControleViewSet', 'create'),
}


def peut_acceder(request, chemin_vue, action):
    view = import_string(chemin_vue)()
    view.request, view.args, view.kwargs, view.format_kwarg = request, (), {}, None
    view.action = action
    return all(p.has_permission(request, view) for p in view.get_permissions())


class MesAccesView(generics.GenericAPIView):
    """Écrans accessibles à l'utilisateur connecté : {cle: bool}."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            cle: peut_acceder(request, chemin, action)
            for cle, (chemin, action) in ACCES_ECRANS.items()
        })

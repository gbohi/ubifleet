"""UbiFleet — Permissions dynamiques (basées sur Role.niveau + DB)"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

# Niveaux de référence (fixes dans le code, correspondent aux rôles système)
NIVEAU_SUPER_ADMIN       = 10
NIVEAU_DG                = 8
NIVEAU_RESPONSABLE_FLOTTE = 6
NIVEAU_GESTIONNAIRE      = 4
NIVEAU_COMPTABLE         = 3
NIVEAU_OPERATEUR         = 2
NIVEAU_CHAUFFEUR         = 1

# Niveau minimum par défaut pour chaque action (fallback si pas en DB)
DEFAULT_ACTION_NIVEAU = {
    'list':                    NIVEAU_OPERATEUR,
    'retrieve':                NIVEAU_OPERATEUR,
    'create':                  NIVEAU_GESTIONNAIRE,
    'update':                  NIVEAU_GESTIONNAIRE,
    'partial_update':          NIVEAU_GESTIONNAIRE,
    'destroy':                 NIVEAU_RESPONSABLE_FLOTTE,
    'valider':                 NIVEAU_OPERATEUR,
    'anomalies':               NIVEAU_OPERATEUR,
    'demarrer':                NIVEAU_GESTIONNAIRE,
    'terminer':                NIVEAU_GESTIONNAIRE,
    'changer_statut':          NIVEAU_GESTIONNAIRE,
    'kilometrage':             NIVEAU_OPERATEUR,
    'changer_immatriculation': NIVEAU_RESPONSABLE_FLOTTE,
    'tableau_de_bord':         NIVEAU_COMPTABLE,
    'toggle_active':           NIVEAU_RESPONSABLE_FLOTTE,
    'reset_password':          NIVEAU_RESPONSABLE_FLOTTE,
}


def get_user_niveau(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    return getattr(user, 'role_niveau', 0)


def has_min_niveau(user, niveau: int) -> bool:
    return get_user_niveau(user) >= niveau


# ── Permissions fixes (pour l'admin système) ─────────────────────────

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_SUPER_ADMIN)


class IsAdminLevel(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_DG)


class IsFleetManager(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_RESPONSABLE_FLOTTE)


class IsGestionnaire(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_GESTIONNAIRE)


class IsComptable(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_COMPTABLE)


class IsOperateur(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_OPERATEUR)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return has_min_niveau(request.user, NIVEAU_GESTIONNAIRE)


class CanManageUsers(BasePermission):
    def has_permission(self, request, view):
        return has_min_niveau(request.user, NIVEAU_RESPONSABLE_FLOTTE)


class IsAgenceUser(BasePermission):
    def has_object_permission(self, request, view, obj):
        if has_min_niveau(request.user, NIVEAU_RESPONSABLE_FLOTTE):
            return True
        return getattr(obj, 'agence_id', None) == request.user.agence_id


# ── Permission DB-driven (principale) ────────────────────────────────

class RoleBasedPermission(BasePermission):
    """
    Logique :
    1. Non authentifié → refusé
    2. super_admin (niveau >= 10) → toujours autorisé
    3. Cherche la règle (role_id, module, action) en DB (via cache)
    4. Règle trouvée → applique autorise=True/False
    5. Pas de règle → fallback sur DEFAULT_ACTION_NIVEAU
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # super_admin passe toujours
        if getattr(user, 'role_niveau', 0) >= 10:
            return True

        action = getattr(view, 'action', None)
        module = getattr(view, 'module', None)
        if not action or not module:
            return True

        role = getattr(user, 'role', None)
        if not role:
            return False

        # 1. Chercher en DB (via cache)
        from apps.accounts.permission_cache import is_allowed
        db_result = is_allowed(role.id, module, action)

        if db_result is not None:
            return db_result

        # 2. Fallback — vérifier via le niveau du rôle
        view_role_map = getattr(view, 'role_map', {})
        required_code = view_role_map.get(action, '')

        if required_code:
            # Convertir le code en niveau
            niveau_map = {
                'super_admin':        NIVEAU_SUPER_ADMIN,
                'dg':                 NIVEAU_DG,
                'responsable_flotte': NIVEAU_RESPONSABLE_FLOTTE,
                'gestionnaire':       NIVEAU_GESTIONNAIRE,
                'comptable':          NIVEAU_COMPTABLE,
                'operateur':          NIVEAU_OPERATEUR,
                'chauffeur':          NIVEAU_CHAUFFEUR,
            }
            required_niveau = niveau_map.get(required_code, NIVEAU_GESTIONNAIRE)
        else:
            required_niveau = DEFAULT_ACTION_NIVEAU.get(action, NIVEAU_GESTIONNAIRE)

        return has_min_niveau(user, required_niveau)

"""
python manage.py init_roles
Crée les 7 rôles système initiaux et les permissions par défaut.
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import Role, PermissionRole

ROLES_SYSTEME = [
    # (code, nom, niveau, description)
    ('super_admin',        'Super Administrateur', 10, 'Accès total au système.'),
    ('dg',                 'Direction Générale',    8, 'Vision globale, validation stratégique.'),
    ('responsable_flotte', 'Responsable Flotte',   6, 'Gestion complète de la flotte.'),
    ('gestionnaire',       'Gestionnaire',          4, 'Opérations courantes de gestion.'),
    ('comptable',          'Comptable',             3, 'Budget, dépenses, reporting financier.'),
    ('operateur',          'Opérateur',             2, 'Saisie des données opérationnelles.'),
    ('chauffeur',          'Chauffeur',             1, 'Consultation et saisie limitées.'),
]

# Permissions par défaut : (code_role, module, action, autorise)
DEFAULT_PERMISSIONS = [
    # ── Véhicules ──
    ('chauffeur',         'vehicules', 'list',     True),
    ('chauffeur',         'vehicules', 'retrieve', True),
    ('operateur',         'vehicules', 'list',     True),
    ('operateur',         'vehicules', 'retrieve', True),
    ('operateur',         'vehicules', 'kilometrage', True),
    ('gestionnaire',      'vehicules', 'create',   True),
    ('gestionnaire',      'vehicules', 'update',   True),
    ('gestionnaire',      'vehicules', 'partial_update', True),
    ('responsable_flotte','vehicules', 'destroy',  True),
    ('responsable_flotte','vehicules', 'changer_immatriculation', True),
    # ── Carburant ──
    ('chauffeur',         'carburant', 'list',     True),
    ('chauffeur',         'carburant', 'retrieve', True),
    ('chauffeur',         'carburant', 'create',   True),
    ('operateur',         'carburant', 'list',     True),
    ('operateur',         'carburant', 'retrieve', True),
    ('operateur',         'carburant', 'create',   True),
    ('operateur',         'carburant', 'valider',  True),
    ('operateur',         'carburant', 'anomalies',True),
    ('gestionnaire',      'carburant', 'update',   True),
    ('gestionnaire',      'carburant', 'partial_update', True),
    ('responsable_flotte','carburant', 'destroy',  True),
    # ── Entretien ──
    ('operateur',         'entretien', 'list',     True),
    ('operateur',         'entretien', 'retrieve', True),
    ('gestionnaire',      'entretien', 'create',   True),
    ('gestionnaire',      'entretien', 'update',   True),
    ('gestionnaire',      'entretien', 'partial_update', True),
    ('gestionnaire',      'entretien', 'demarrer', True),
    ('gestionnaire',      'entretien', 'terminer', True),
    ('responsable_flotte','entretien', 'destroy',  True),
    # ── Sinistres ──
    ('operateur',         'sinistres', 'list',     True),
    ('operateur',         'sinistres', 'retrieve', True),
    ('gestionnaire',      'sinistres', 'create',   True),
    ('gestionnaire',      'sinistres', 'update',   True),
    ('gestionnaire',      'sinistres', 'partial_update', True),
    ('gestionnaire',      'sinistres', 'changer_statut', True),
    ('responsable_flotte','sinistres', 'destroy',  True),
    # ── Budget ──
    ('comptable',         'budget',    'list',     True),
    ('comptable',         'budget',    'retrieve', True),
    ('comptable',         'budget',    'tableau_de_bord', True),
    ('gestionnaire',      'budget',    'create',   True),
    ('gestionnaire',      'budget',    'update',   True),
    ('gestionnaire',      'budget',    'partial_update', True),
    ('responsable_flotte','budget',    'destroy',  True),
    # ── Chauffeurs ──
    ('operateur',         'chauffeurs','list',     True),
    ('operateur',         'chauffeurs','retrieve', True),
    ('gestionnaire',      'chauffeurs','create',   True),
    ('gestionnaire',      'chauffeurs','update',   True),
    ('gestionnaire',      'chauffeurs','partial_update', True),
    ('responsable_flotte','chauffeurs','destroy',  True),
    # ── Alertes ──
    ('chauffeur',         'alertes', 'list',     True),
    ('chauffeur',         'alertes', 'retrieve', True),
    ('operateur',         'alertes', 'list',     True),
    ('operateur',         'alertes', 'retrieve', True),
    # ── Total Import ──
    ('responsable_flotte','total_import', 'list',     True),
    ('responsable_flotte','total_import', 'retrieve', True),
    ('responsable_flotte','total_import', 'upload',   True),
    ('responsable_flotte','total_import', 'stats',    True),
    ('gestionnaire',      'total_import', 'list',     True),
    ('gestionnaire',      'total_import', 'retrieve', True),
    ('gestionnaire',      'total_import', 'upload',   True),
    ('gestionnaire',      'total_import', 'stats',    True),
    ('comptable',         'total_import', 'list',     True),
    ('comptable',         'total_import', 'retrieve', True),
    ('comptable',         'total_import', 'stats',    True),
    # ── Agences ──
    ('responsable_flotte','agences', 'list',     True),
    ('responsable_flotte','agences', 'retrieve', True),
    ('responsable_flotte','agences', 'create',   True),
    ('responsable_flotte','agences', 'update',   True),
    ('responsable_flotte','agences', 'partial_update', True),
    # ── Relevés Km ──
    ('chauffeur',         'releves_km','list',     True),
    ('chauffeur',         'releves_km','retrieve', True),
    ('chauffeur',         'releves_km','create',   True),
    ('operateur',         'releves_km','list',     True),
    ('operateur',         'releves_km','retrieve', True),
    ('operateur',         'releves_km','create',   True),
    ('gestionnaire',      'releves_km','update',   True),
    ('responsable_flotte','releves_km','destroy',  True),
    # ── Affectations ──
    ('operateur',         'affectations','list',    True),
    ('operateur',         'affectations','retrieve',True),
    ('gestionnaire',      'affectations','create',  True),
    ('gestionnaire',      'affectations','update',  True),
    ('gestionnaire',      'affectations','partial_update', True),
    ('responsable_flotte','affectations','destroy', True),
    # ── Utilisateurs ──
    ('responsable_flotte','users', 'list',          True),
    ('responsable_flotte','users', 'retrieve',      True),
    ('responsable_flotte','users', 'create',        True),
    ('responsable_flotte','users', 'update',        True),
    ('responsable_flotte','users', 'toggle_active', True),
    ('responsable_flotte','users', 'reset_password',True),
]


class Command(BaseCommand):
    help = 'Initialise les rôles système et les permissions par défaut'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Réinitialiser les permissions existantes')

    def handle(self, *args, **options):
        # 1. Créer les rôles système
        roles_map = {}
        created_r = updated_r = 0
        for code, nom, niveau, desc in ROLES_SYSTEME:
            role, created = Role.objects.update_or_create(
                code=code,
                defaults={
                    'nom': nom, 'niveau': niveau,
                    'description': desc, 'is_system': True, 'is_active': True,
                }
            )
            roles_map[code] = role
            if created: created_r += 1
            else:        updated_r += 1

        self.stdout.write(f'Rôles : {created_r} créés, {updated_r} mis à jour.')

        # 2. Permissions
        if options['reset']:
            PermissionRole.objects.all().delete()
            self.stdout.write('Permissions réinitialisées.')

        created_p = updated_p = 0
        for role_code, module, action, autorise in DEFAULT_PERMISSIONS:
            role = roles_map.get(role_code)
            if not role:
                continue
            _, created = PermissionRole.objects.update_or_create(
                role=role, module=module, action=action,
                defaults={'autorise': autorise}
            )
            if created: created_p += 1
            else:        updated_p += 1

        # Supprimer les permissions dont l'action n'est pas valide pour le module
        from apps.accounts.models import PermissionRole as PR
        deleted = 0
        for perm in PR.objects.all():
            valid_actions = Role.objects.none()  # placeholder
            module_actions = {
                'vehicules':   ['list','retrieve','create','update','partial_update','destroy','kilometrage','changer_immatriculation'],
                'carburant':   ['list','retrieve','create','update','partial_update','destroy','valider','anomalies'],
                'entretien':   ['list','retrieve','create','update','partial_update','destroy','demarrer','terminer'],
                'sinistres':   ['list','retrieve','create','update','partial_update','destroy','changer_statut'],
                'budget':      ['list','retrieve','create','update','partial_update','destroy','tableau_de_bord'],
                'chauffeurs':  ['list','retrieve','create','update','partial_update','destroy'],
                'releves_km':  ['list','retrieve','create','update','partial_update','destroy'],
                'affectations':['list','retrieve','create','update','partial_update','destroy'],
                'users':       ['list','retrieve','create','update','partial_update','destroy','toggle_active','reset_password'],
                'roles':       ['list','retrieve','create','update','partial_update','destroy'],
                'parametres':  ['list','retrieve','create','update','partial_update','destroy'],
                'agences':     ['list','retrieve','create','update','partial_update','destroy'],
                'total_import': ['list','retrieve','upload','stats'],
                'alertes':     ['list','retrieve'],
            }
            allowed = module_actions.get(perm.module, [])
            if perm.action not in allowed:
                perm.delete()
                deleted += 1

        from apps.accounts.permission_cache import invalidate
        invalidate()
        self.stdout.write(
            self.style.SUCCESS(
                f'Permissions : {created_p} créées, {updated_p} mises à jour, {deleted} obsolètes supprimées.'
            )
        )

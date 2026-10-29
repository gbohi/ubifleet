"""
Commande : python manage.py init_permissions
Initialise les PermissionRole en DB depuis les role_map par défaut.
À lancer après les migrations.
"""

from django.core.management.base import BaseCommand
from apps.accounts.models import User, PermissionRole

DEFAULT_PERMISSIONS = [
    # (role, module, action, autorise)
    # ── Véhicules ──
    ('chauffeur',         'vehicules', 'list',     True),
    ('chauffeur',         'vehicules', 'retrieve', True),
    ('operateur',         'vehicules', 'list',     True),
    ('operateur',         'vehicules', 'retrieve', True),
    ('operateur',         'vehicules', 'kilometrage', True),
    ('gestionnaire',      'vehicules', 'list',     True),
    ('gestionnaire',      'vehicules', 'retrieve', True),
    ('gestionnaire',      'vehicules', 'create',   True),
    ('gestionnaire',      'vehicules', 'update',   True),
    ('gestionnaire',      'vehicules', 'partial_update', True),
    ('gestionnaire',      'vehicules', 'kilometrage', True),
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
    ('operateur',         'entretien', 'stats',    True),
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
    ('operateur',         'affectations','list',   True),
    ('operateur',         'affectations','retrieve',True),
    ('gestionnaire',      'affectations','create', True),
    ('gestionnaire',      'affectations','update', True),
    ('gestionnaire',      'affectations','partial_update', True),
    ('responsable_flotte','affectations','destroy',True),

    # ── Utilisateurs ──
    ('responsable_flotte','users', 'list',         True),
    ('responsable_flotte','users', 'retrieve',     True),
    ('responsable_flotte','users', 'create',       True),
    ('responsable_flotte','users', 'update',       True),
    ('responsable_flotte','users', 'toggle_active',True),
    ('responsable_flotte','users', 'reset_password',True),
    ('super_admin',       'users', 'destroy',      True),
]


class Command(BaseCommand):
    help = 'Initialise les permissions par rôle en base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Supprimer toutes les permissions avant de réinitialiser'
        )

    def handle(self, *args, **options):
        if options['reset']:
            count = PermissionRole.objects.count()
            PermissionRole.objects.all().delete()
            self.stdout.write(f'  {count} permissions supprimées.')

        created = updated = 0
        for role, module, action, autorise in DEFAULT_PERMISSIONS:
            obj, was_created = PermissionRole.objects.update_or_create(
                role=role, module=module, action=action,
                defaults={'autorise': autorise}
            )
            if was_created:
                created += 1
            else:
                updated += 1

        from apps.accounts.permission_cache import invalidate
        invalidate()

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ {created} permissions créées, {updated} mises à jour.'
            )
        )

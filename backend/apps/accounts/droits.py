"""UbiFleet — Droits effectifs d'un rôle (matrice des permissions).

Le droit appliqué par l'API pour (rôle, module, action) est :
  1. la règle enregistrée (PermissionRole) si elle existe ;
  2. sinon le niveau minimum déclaré par les vues du module (role_map),
     ou à défaut DEFAULT_ACTION_NIVEAU.
Ce module calcule ce droit pour l'afficher fidèlement dans l'écran
Permissions, et ne garder en base que les écarts au comportement par défaut.
"""
import importlib
import inspect
from functools import lru_cache

from django.apps import apps as django_apps

from .permissions import (
    DEFAULT_ACTION_NIVEAU, NIVEAU_CHAUFFEUR, NIVEAU_COMPTABLE, NIVEAU_DG, NIVEAU_GESTIONNAIRE,
    NIVEAU_OPERATEUR, NIVEAU_RESPONSABLE_FLOTTE, NIVEAU_SUPER_ADMIN, RoleBasedPermission,
)

NIVEAUX_CODES = {
    'super_admin': NIVEAU_SUPER_ADMIN, 'dg': NIVEAU_DG, 'responsable_flotte': NIVEAU_RESPONSABLE_FLOTTE,
    'gestionnaire': NIVEAU_GESTIONNAIRE, 'comptable': NIVEAU_COMPTABLE, 'operateur': NIVEAU_OPERATEUR,
    'chauffeur': NIVEAU_CHAUFFEUR,
}


@lru_cache(maxsize=1)
def niveaux_requis():
    """{(module, action_db): niveau minimum} d'après les vues à permissions dynamiques."""
    requis = {}
    for app in django_apps.get_app_configs():
        if not app.name.startswith('apps.'):
            continue
        try:
            mod = importlib.import_module(f'{app.name}.views')
        except ImportError:
            continue
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            module = getattr(cls, 'module', None)
            if not module or RoleBasedPermission not in getattr(cls, 'permission_classes', []):
                continue
            traduction = getattr(cls, 'permission_actions', {})
            for action, code in getattr(cls, 'role_map', {}).items():
                cle = (module, traduction.get(action, action))
                niveau = NIVEAUX_CODES.get(code, NIVEAU_GESTIONNAIRE)
                requis[cle] = min(requis.get(cle, niveau), niveau)
    return requis


def niveau_par_defaut(module, action):
    return niveaux_requis().get((module, action), DEFAULT_ACTION_NIVEAU.get(action, NIVEAU_GESTIONNAIRE))


def autorise_par_defaut(role, module, action):
    return role.niveau >= NIVEAU_SUPER_ADMIN or role.niveau >= niveau_par_defaut(module, action)

"""UbiFleet — Fenêtre de saisie des pleins et des relevés kilométriques.

Paramètre `fenetre_saisie_<domaine>_jours` (0 = désactivée) :
avec N jours, seules les dates d'aujourd'hui à J-(N-1) sont acceptées.
Une donnée datée hors de la fenêtre est figée : ni modification ni suppression.

Exception : la permission « Saisie hors délai » (action `saisie_hors_delai`
du module, réglable par rôle) autorise la saisie et la correction hors fenêtre ;
chaque opération de ce type est tracée sur la donnée (par qui, quand).

Les dates futures sont toujours refusées. « Aujourd'hui » est la date du
serveur (fuseau Africa/Abidjan), jamais celle de l'appareil de l'utilisateur.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace

from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

CARBURANT, RELEVES = 'carburant', 'releves'

# domaine → (module de permission, libellé de la donnée)
DOMAINES = {
    CARBURANT: ('carburant',  'plein'),
    RELEVES:   ('releves_km', 'relevé'),
}
JOURS_MAX = 365
ACTION_HORS_DELAI = 'saisie_hors_delai'


def cle(domaine: str) -> str:
    return f'fenetre_saisie_{domaine}_jours'


def nb_jours(domaine: str) -> int:
    from apps.parametrage.models import Parametre
    try:
        return max(0, int(Parametre.get(cle(domaine), 0) or 0))
    except (TypeError, ValueError):
        return 0


def peut_saisir_hors_delai(user, domaine: str) -> bool:
    """Évalue la permission « Saisie hors délai » comme une action de vue
    (règle en base, sinon niveau par défaut : responsable flotte)."""
    from apps.accounts.permissions import action_autorisee
    vue = SimpleNamespace(module=DOMAINES[domaine][0], role_map={ACTION_HORS_DELAI: 'responsable_flotte'})
    return action_autorisee(user, vue, ACTION_HORS_DELAI)


@dataclass
class Fenetre:
    domaine: str
    jours: int              # 0 = désactivée
    aujourdhui: date
    hors_delai: bool        # l'utilisateur peut saisir hors fenêtre

    @property
    def date_min(self):
        return self.aujourdhui - timedelta(days=self.jours - 1) if self.jours else None

    def dans_fenetre(self, d: date) -> bool:
        return self.date_min is None or self.date_min <= d <= self.aujourdhui

    def verrouille(self, d) -> bool:
        """Donnée existante figée pour cet utilisateur."""
        return bool(d) and not self.hors_delai and not self.dans_fenetre(d)

    def controler_date(self, d: date, champ: str) -> bool:
        """Valide une date saisie ; renvoie True si la saisie est hors délai."""
        if d > self.aujourdhui:
            raise serializers.ValidationError({champ: "La date ne peut pas être dans le futur."})
        if self.dans_fenetre(d):
            return False
        if not self.hors_delai:
            raise serializers.ValidationError({champ: (
                f"Date hors de la fenêtre de saisie : seules les dates du "
                f"{self.date_min:%d/%m/%Y} au {self.aujourdhui:%d/%m/%Y} sont acceptées. "
                "Une saisie plus ancienne nécessite le droit « Saisie hors délai ».")})
        return True

    def controler_modification(self, d_actuelle) -> bool:
        """Refuse de toucher une donnée figée ; renvoie True si hors délai."""
        if not d_actuelle or self.dans_fenetre(d_actuelle):
            return False
        if not self.hors_delai:
            libelle = DOMAINES[self.domaine][1]
            raise PermissionDenied(
                f"Ce {libelle} du {d_actuelle:%d/%m/%Y} est figé : il est sorti de la fenêtre "
                f"de saisie ({self.jours} jour{'s' if self.jours > 1 else ''}). "
                "Seul un utilisateur disposant du droit « Saisie hors délai » peut le corriger.")
        return True

    def en_dict(self):
        return {
            'jours': self.jours,
            'active': bool(self.jours),
            'date_min': self.date_min,
            'date_max': self.aujourdhui,
            'hors_delai': self.hors_delai,
        }


def fenetre(user, domaine: str) -> Fenetre:
    return Fenetre(domaine, nb_jours(domaine), timezone.localdate(),
                   peut_saisir_hors_delai(user, domaine))


def tracer_hors_delai(user):
    """Champs de traçabilité d'une saisie hors délai."""
    return {'saisie_hors_delai': True, 'hors_delai_par': user, 'hors_delai_le': timezone.now()}


class FenetreSaisieSerializerMixin(serializers.Serializer):
    """Expose l'état de la donnée vis-à-vis de la fenêtre de saisie :
    `verrouille` (figée pour l'utilisateur courant) et la trace hors délai.
    À combiner avec un ModelSerializer ; définir `domaine_saisie` et `champ_date`."""
    domaine_saisie = None
    champ_date = None

    verrouille         = serializers.SerializerMethodField()
    hors_fenetre       = serializers.SerializerMethodField()
    modifiable         = serializers.SerializerMethodField()
    supprimable        = serializers.SerializerMethodField()
    hors_delai_par_nom = serializers.SerializerMethodField()

    CHAMPS_FENETRE = ['verrouille', 'hors_fenetre', 'modifiable', 'supprimable',
                      'saisie_hors_delai', 'hors_delai_par', 'hors_delai_par_nom', 'hors_delai_le']
    LECTURE_SEULE_FENETRE = ['saisie_hors_delai', 'hors_delai_par', 'hors_delai_le']

    def _fenetre(self):
        if '_fenetre_saisie' not in self.context:
            request = self.context.get('request')
            self.context['_fenetre_saisie'] = (
                fenetre(request.user, self.domaine_saisie) if request else None)
        return self.context['_fenetre_saisie']

    def get_verrouille(self, obj):
        f = self._fenetre()
        return bool(f and f.verrouille(getattr(obj, self.champ_date)))

    def get_hors_fenetre(self, obj):
        """Date sortie de la fenêtre : une correction exigera un motif."""
        f = self._fenetre()
        return bool(f and not f.dans_fenetre(getattr(obj, self.champ_date)))

    def _droit_role(self, action):
        """Droit du rôle sur l'action (indépendamment de l'auteur), mis en cache."""
        cle_cache = f'_droit_{action}'
        if cle_cache not in self.context:
            from apps.accounts.permissions import action_autorisee
            request, vue = self.context.get('request'), self.context.get('view')
            self.context[cle_cache] = bool(request and vue and action_autorisee(request.user, vue, action))
        return self.context[cle_cache]

    def _corrigeable(self, obj, action):
        f, request = self._fenetre(), self.context.get('request')
        if not f or not request or f.verrouille(getattr(obj, self.champ_date)):
            return False
        auteur = obj.created_by_id is not None and obj.created_by_id == request.user.id
        return self._droit_role(action) or (auteur and f.dans_fenetre(getattr(obj, self.champ_date)))

    def get_modifiable(self, obj):
        return self._corrigeable(obj, 'partial_update')

    def get_supprimable(self, obj):
        return self._corrigeable(obj, 'destroy')

    def get_hors_delai_par_nom(self, obj):
        u = obj.hors_delai_par
        return (u.full_name or u.username) if u else None

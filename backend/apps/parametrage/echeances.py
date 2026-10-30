"""UbiFleet — Échéances : règle unique pour l'État du parc et les alertes.

Chaque échéance a deux seuils, exprimés dans son unité (jours ou km) :
- « attention » : voyant orange, alerte de priorité normale ;
- « urgent »    : voyant rouge, alerte de priorité haute ;
- échéance dépassée : voyant « dépassé », alerte critique.

Les seuils sont stockés dans Parametre sous les clés
`echeance_<code>_attention` et `echeance_<code>_urgent`.
"""

from dataclasses import dataclass

JOURS, KM = 'jours', 'km'


@dataclass(frozen=True)
class Echeance:
    code: str
    libelle: str
    unite: str
    attention_defaut: int
    urgent_defaut: int


ECHEANCES = {e.code: e for e in [
    Echeance('assurance',       'Assurance',          JOURS, 30, 7),
    Echeance('ct',              'Contrôle technique', JOURS, 30, 7),
    Echeance('carte_transport', 'Carte de transport', JOURS, 30, 7),
    Echeance('vignette',        'Vignette',           JOURS, 30, 7),
    Echeance('permis',          'Permis de conduire', JOURS, 60, 15),
    Echeance('revision',        'Révision',           KM,  2000, 500),
    Echeance('pneus',           'Pneus',              KM,  2000, 500),
]}

# Seuil d'anomalie de consommation (% au-dessus de la moyenne du véhicule)
CLE_CONSO_ANOMALIE = 'conso_anomalie_pct'
CONSO_ANOMALIE_DEFAUT = 30

NC, DEPASSE, URGENT, ATTENTION, OK = 'nc', 'depasse', 'urgent', 'attention', 'ok'


def cle(code: str, niveau: str) -> str:
    return f'echeance_{code}_{niveau}'


def seuils(code: str) -> tuple[int, int]:
    """(attention, urgent) pour une échéance, depuis les paramètres."""
    from .models import Parametre
    e = ECHEANCES[code]
    return (
        int(Parametre.get(cle(code, 'attention'), e.attention_defaut)),
        int(Parametre.get(cle(code, 'urgent'), e.urgent_defaut)),
    )


def niveau(restant, attention: int, urgent: int) -> str:
    """Niveau d'une échéance selon ce qui reste (jours ou km)."""
    if restant is None:
        return NC
    if restant <= 0:
        return DEPASSE
    if restant <= urgent:
        return URGENT
    if restant <= attention:
        return ATTENTION
    return OK


def tous_les_seuils() -> dict:
    """{code: (attention, urgent)} — une requête par paramètre, à appeler
    une fois avant de traiter une liste de véhicules."""
    return {code: seuils(code) for code in ECHEANCES}


def seuil_conso_anomalie() -> float:
    from .models import Parametre
    return float(Parametre.get(CLE_CONSO_ANOMALIE, CONSO_ANOMALIE_DEFAUT))

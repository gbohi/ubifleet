"""UbiFleet — Prises de carburant reportées dans les dépenses (budget, coûts).

Cf. apps.budget.automatiques : chaque prise d'un montant non nul a sa dépense
« Carburant », créée, mise à jour et supprimée avec elle.
"""

from apps.budget.automatiques import REF_PRISE, champs_prise, supprimer, synchroniser  # noqa: F401


def synchroniser_depense(prise):
    from apps.budget.models import DepenseVehicule
    synchroniser(DepenseVehicule, REF_PRISE, prise, champs_prise(prise))


def supprimer_depense(prise_pk):
    supprimer(REF_PRISE, prise_pk)

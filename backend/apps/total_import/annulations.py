"""UbiFleet — Annulations dans les transactions TotalEnergies.

Une annulation est une transaction de volume négatif. Elle désigne la vente
qu'elle annule de deux façons :
  - annulation automatique (timeout) : code d'autorisation de la vente précédé
    d'un « - » (« -3451474 » annule « 3451474 ») ;
  - annulation manuelle (« ANNULER Vente en Post Payé ») : code propre ; la
    vente annulée est la dernière vente antérieure du même véhicule, le même
    jour, de même volume et même montant, pas encore annulée.

Le résultat est enregistré sur chaque transaction (est_annulation,
est_annulee) : liste, synthèse, rapprochement et consommation facturée ne
comptent que les ventes effectives (ni annulation ni vente annulée).
"""

from datetime import time


def _quand(t):
    return (t.date_transaction, t.heure_transaction or time(23, 59, 59))


def marquer_annulations(immatriculations=None):
    """Recalcule est_annulation / est_annulee (pour les plaques données, ou toutes)."""
    from .models import TransactionCarburant
    qs = TransactionCarburant.objects.all()
    if immatriculations is not None:
        qs = qs.filter(immatriculation__in=set(immatriculations))
    transactions = list(qs.only('id', 'immatriculation', 'date_transaction', 'heure_transaction', 'volume',
                                'montant', 'code_autorisation', 'est_annulation', 'est_annulee'))
    par_code = {t.code_autorisation: t for t in transactions if (t.volume or 0) > 0 and t.code_autorisation}
    annulees = set()
    manuelles = []
    for t in transactions:
        if (t.volume or 0) >= 0:
            continue
        code = t.code_autorisation or ''
        vente = par_code.get(code[1:]) if code.startswith('-') else None
        if vente:
            annulees.add(vente.pk)
        else:
            manuelles.append(t)
    for a in sorted(manuelles, key=_quand):
        candidates = [v for v in transactions
                      if (v.volume or 0) > 0 and v.pk not in annulees and v.immatriculation == a.immatriculation
                      and v.date_transaction == a.date_transaction and v.volume == -a.volume
                      and (v.montant or 0) == -(a.montant or 0) and _quand(v) <= _quand(a)]
        if candidates:
            annulees.add(max(candidates, key=_quand).pk)

    a_maj = []
    for t in transactions:
        est_annulation, est_annulee = (t.volume or 0) < 0, t.pk in annulees
        if (t.est_annulation, t.est_annulee) != (est_annulation, est_annulee):
            t.est_annulation, t.est_annulee = est_annulation, est_annulee
            a_maj.append(t)
    TransactionCarburant.objects.bulk_update(a_maj, ['est_annulation', 'est_annulee'], batch_size=500)
    return len(a_maj)

"""UbiFleet — Prises de carburant reportées dans les dépenses (budget, coûts).

Chaque prise de carburant d'un montant non nul a sa dépense « Carburant »
(DepenseVehicule, référence ref_objet_type = REF_PRISE), créée, mise à jour
et supprimée avec elle : le carburant entre dans les rapports de coûts et le
réalisé du budget sans ressaisie. Ces dépenses ne se modifient que par la
prise (cf. budget.views.DepenseViewSet).
"""

REF_PRISE = 'prise_carburant'


def synchroniser_depense(prise):
    from apps.budget.models import DepenseVehicule
    from apps.parametrage.models import CATEGORIE_CARBURANT
    qs = DepenseVehicule.objects.filter(ref_objet_type=REF_PRISE, ref_objet_id=prise.pk)
    if not prise.montant_fcfa or prise.montant_fcfa <= 0:
        qs.delete()
        return
    station = prise.station.nom if prise.station_id else ''
    champs = {
        'vehicule_id': prise.vehicule_id, 'agence_id': prise.agence_id,
        'categorie': CATEGORIE_CARBURANT, 'date_depense': prise.date_plein,
        'montant': prise.montant_fcfa,
        'description': f"Prise de carburant — {prise.volume_litres} L"
                       + (f" ({prise.tournee.code})" if prise.tournee_id else ''),
        'fournisseur': station, 'numero_facture': prise.bon_carburant or '',
    }
    if not qs.update(**champs):
        DepenseVehicule.objects.create(ref_objet_type=REF_PRISE, ref_objet_id=prise.pk,
                                       created_by=prise.created_by, **champs)


def supprimer_depense(prise_pk):
    from apps.budget.models import DepenseVehicule
    DepenseVehicule.objects.filter(ref_objet_type=REF_PRISE, ref_objet_id=prise_pk).delete()

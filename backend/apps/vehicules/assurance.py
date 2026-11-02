"""UbiFleet — Fin de couverture d'assurance d'un véhicule.

L'assurance est connue par deux sources : les contrats saisis dans
Sinistres & Assurances et les documents « Assurance » de la fiche véhicule.
La couverture retenue est la date de fin la plus lointaine des deux.
"""


def fins_assurance(vehicule_ids=None):
    """{vehicule_id: date de fin d'assurance la plus lointaine}."""
    from django.db.models import Max
    from apps.sinistres.models import ContratAssurance
    from .models import DocumentVehicule, TypeDocumentVehicule

    contrats = ContratAssurance.objects.filter(is_active=True)
    docs = DocumentVehicule.objects.filter(
        type_document__code=TypeDocumentVehicule.CODE_ASSURANCE, date_expiration__isnull=False)
    if vehicule_ids is not None:
        contrats = contrats.filter(vehicule_id__in=vehicule_ids)
        docs = docs.filter(vehicule_id__in=vehicule_ids)
    fins = {}
    for vid, fin in list(contrats.values_list('vehicule_id').annotate(f=Max('date_fin'))) + \
            list(docs.values_list('vehicule_id').annotate(f=Max('date_expiration'))):
        if fin and (vid not in fins or fin > fins[vid]):
            fins[vid] = fin
    return fins

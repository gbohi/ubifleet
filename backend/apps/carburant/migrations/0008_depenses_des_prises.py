"""Les prises de carburant existantes entrent dans les dépenses du budget
(une dépense « Carburant » par prise d'un montant non nul)."""

from django.db import migrations


def reporter(apps, schema_editor):
    Prise = apps.get_model('carburant', 'PleinsCarburant')
    Depense = apps.get_model('budget', 'DepenseVehicule')
    deja = set(Depense.objects.filter(ref_objet_type='prise_carburant').values_list('ref_objet_id', flat=True))
    nouvelles = []
    for p in Prise.objects.filter(montant_fcfa__gt=0).select_related('station', 'tournee').iterator():
        if p.pk in deja:
            continue
        nouvelles.append(Depense(
            ref_objet_type='prise_carburant', ref_objet_id=p.pk, vehicule_id=p.vehicule_id,
            agence_id=p.agence_id, categorie='carburant', date_depense=p.date_plein, montant=p.montant_fcfa,
            description=f"Prise de carburant — {p.volume_litres} L" + (f" ({p.tournee.code})" if p.tournee_id else ''),
            fournisseur=p.station.nom if p.station_id else '', numero_facture=p.bon_carburant or '',
            created_by_id=p.created_by_id,
        ))
    Depense.objects.bulk_create(nouvelles, batch_size=500)


def annuler(apps, schema_editor):
    apps.get_model('budget', 'DepenseVehicule').objects.filter(ref_objet_type='prise_carburant').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('carburant', '0007_reprise_tournees'),
        ('budget', '0001_squashed'),
    ]

    operations = [migrations.RunPython(reporter, annuler)]

"""Données initiales : affectations/usages et statuts véhicule."""
from django.db import migrations

AFFECTATIONS = [
    ('DIRECTION', 'Véhicule de direction'),
    ('COMMERCIAL', 'Véhicule commercial'),
    ('LIVRAISON', 'Livraison'),
    ('TOURNEE', 'Tournée'),
    ('POOL', 'Véhicule de pool'),
    ('MAINTENANCE', 'Maintenance / Technique'),
    ('AUTRE', 'Autre usage'),
]

STATUTS = [
    ('en_service',   'En service',       'green'),
    ('en_revision',  'En révision',      'orange'),
    ('en_panne',     'En panne',         'red'),
    ('immobilise',   'Immobilisé',       'red'),
    ('vendu',        'Vendu / Réformé',  'gray'),
    ('accidente',    'Accidenté',        'red'),
    ('en_attente',   'En attente mise en service', 'blue'),
]


def insert_data(apps, schema_editor):
    AffectationUsage = apps.get_model('parametrage', 'AffectationUsage')
    StatutVehicule   = apps.get_model('parametrage', 'StatutVehicule')
    for code, libelle in AFFECTATIONS:
        AffectationUsage.objects.get_or_create(code=code, defaults={'libelle': libelle})
    for code, libelle, couleur in STATUTS:
        StatutVehicule.objects.get_or_create(code=code, defaults={'libelle': libelle, 'couleur': couleur})


def delete_data(apps, schema_editor):
    apps.get_model('parametrage', 'AffectationUsage').objects.all().delete()
    apps.get_model('parametrage', 'StatutVehicule').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('parametrage', '0004_affectationusage_statutvehicule')]
    operations   = [migrations.RunPython(insert_data, delete_data)]

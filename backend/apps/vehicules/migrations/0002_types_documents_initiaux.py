"""Migration de données : types de documents véhicule initiaux."""
from django.db import migrations

TYPES = [
    {'code': 'carte_grise',     'libelle': 'Carte grise',             'actif': True, 'ordre': 1},
    {'code': 'assurance',       'libelle': 'Attestation assurance',   'actif': True, 'ordre': 2},
    {'code': 'ct',              'libelle': 'Contrôle technique',      'actif': True, 'ordre': 3},
    {'code': 'carte_transport', 'libelle': 'Carte de transport',      'actif': True, 'ordre': 4},
    {'code': 'vignette',        'libelle': 'Vignette',                'actif': True, 'ordre': 5},
    {'code': 'autre',           'libelle': 'Autre',                   'actif': True, 'ordre': 99},
]


def insert_types(apps, schema_editor):
    TypeDocumentVehicule = apps.get_model('vehicules', 'TypeDocumentVehicule')
    for t in TYPES:
        TypeDocumentVehicule.objects.get_or_create(code=t['code'], defaults=t)


def remove_types(apps, schema_editor):
    TypeDocumentVehicule = apps.get_model('vehicules', 'TypeDocumentVehicule')
    TypeDocumentVehicule.objects.filter(code__in=[t['code'] for t in TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vehicules', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(insert_types, remove_types),
    ]

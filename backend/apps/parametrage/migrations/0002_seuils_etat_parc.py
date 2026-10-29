"""Migration de données : seuils d'alerte État du Parc."""
from django.db import migrations


SEUILS = [
    {
        'cle': 'etat_parc_km_urgent',
        'valeur': '500',
        'description': 'Seuil km URGENT pour révision et pneus (État du Parc)',
        'categorie': 'alertes',
        'type_valeur': 'int',
    },
    {
        'cle': 'etat_parc_km_attention',
        'valeur': '2000',
        'description': 'Seuil km ATTENTION pour révision et pneus (État du Parc)',
        'categorie': 'alertes',
        'type_valeur': 'int',
    },
    {
        'cle': 'etat_parc_jours_urgent',
        'valeur': '7',
        'description': 'Seuil jours URGENT pour documents véhicule (État du Parc)',
        'categorie': 'alertes',
        'type_valeur': 'int',
    },
    {
        'cle': 'etat_parc_jours_attention',
        'valeur': '30',
        'description': 'Seuil jours ATTENTION pour documents véhicule (État du Parc)',
        'categorie': 'alertes',
        'type_valeur': 'int',
    },
]


def insert_seuils(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    for data in SEUILS:
        Parametre.objects.get_or_create(cle=data['cle'], defaults=data)


def remove_seuils(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    Parametre.objects.filter(cle__in=[d['cle'] for d in SEUILS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('parametrage', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(insert_seuils, remove_seuils),
    ]

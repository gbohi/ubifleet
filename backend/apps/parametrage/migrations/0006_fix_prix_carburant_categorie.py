"""Corrige la catégorie de prix_carburant_litre pour qu'il apparaisse
dans l'onglet Alertes des paramètres (chargé par getAll('alertes'))."""
from django.db import migrations


def fix_categorie(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    Parametre.objects.filter(cle='prix_carburant_litre').update(categorie='alertes')


def revert_categorie(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    Parametre.objects.filter(cle='prix_carburant_litre').update(categorie='carburant')


class Migration(migrations.Migration):
    dependencies = [
        ('parametrage', '0002_data_initiaux'),
        ('parametrage', '0005_data_initiaux'),
    ]
    operations = [migrations.RunPython(fix_categorie, revert_categorie)]

"""Anomalie de consommation jugée sur les 3 dernières prises, seuil 40 %
(réglables dans Paramètres › Seuils), puis recalcul des prises existantes."""

from django.db import migrations


def regler(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    for cle, valeur, description in (
            ('conso_anomalie_pct', '40', "Seuil d'anomalie de consommation (% au-dessus de la moyenne du véhicule)"),
            ('conso_anomalie_fenetre', '3', "Nombre de prises jugées ensemble pour l'anomalie de consommation")):
        Parametre.objects.update_or_create(cle=cle, defaults={
            'valeur': valeur, 'type_valeur': 'int', 'categorie': 'alertes', 'description': description})


def recalculer(apps, schema_editor):
    # Statut, motif et alertes des prises existantes selon la nouvelle règle
    from django.core.management import call_command
    call_command('recalculer_consommations', '--alertes', '--depuis', '3650', verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('parametrage', '0009_referentiels_depenses_sinistres'),
        ('carburant', '0008_depenses_des_prises'),
        ('total_import', '0002_annulations'),
        ('alertes', '0003_alerte_tournee_ouverte'),
    ]

    operations = [
        migrations.RunPython(regler, migrations.RunPython.noop),
        migrations.RunPython(recalculer, migrations.RunPython.noop),
    ]

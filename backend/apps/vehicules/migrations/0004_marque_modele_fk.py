"""Convertit Vehicule.marque et Vehicule.modele (CharField) en FK vers
parametrage.MarqueVehicule / ModeleVehicule.

Étapes :
1. Renommer les anciens champs en marque_old / modele_old
2. Ajouter les nouveaux champs FK (null)
3. Migration de données : créer les Marques/Modèles distincts existants
   puis lier chaque véhicule
4. Supprimer les anciens champs
"""
from django.db import migrations, models
import django.db.models.deletion


def convertir_donnees(apps, schema_editor):
    Vehicule       = apps.get_model('vehicules', 'Vehicule')
    MarqueVehicule = apps.get_model('parametrage', 'MarqueVehicule')
    ModeleVehicule = apps.get_model('parametrage', 'ModeleVehicule')

    for v in Vehicule.objects.all():
        marque_txt = (v.marque_old or '').strip()
        modele_txt = (v.modele_old or '').strip()

        marque_obj = None
        if marque_txt:
            marque_obj = MarqueVehicule.objects.filter(libelle__iexact=marque_txt).first()
            if not marque_obj:
                marque_obj = MarqueVehicule.objects.create(libelle=marque_txt)

        modele_obj = None
        if modele_txt and marque_obj:
            modele_obj = ModeleVehicule.objects.filter(
                marque=marque_obj, libelle__iexact=modele_txt
            ).first()
            if not modele_obj:
                modele_obj = ModeleVehicule.objects.create(
                    marque=marque_obj, libelle=modele_txt
                )

        v.marque = marque_obj
        v.modele = modele_obj
        v.save(update_fields=['marque', 'modele'])


def reverse_donnees(apps, schema_editor):
    Vehicule = apps.get_model('vehicules', 'Vehicule')
    for v in Vehicule.objects.select_related('marque', 'modele'):
        v.marque_old = v.marque.libelle if v.marque else ''
        v.modele_old = v.modele.libelle if v.modele else ''
        v.save(update_fields=['marque_old', 'modele_old'])


class Migration(migrations.Migration):
    dependencies = [
        ('vehicules',   '0003_vehicule_fk_statut_affectation'),
        ('parametrage', '0007_marque_modele'),
    ]

    operations = [
        # 1. Renommer les anciens champs
        migrations.RenameField('vehicule', 'marque', 'marque_old'),
        migrations.RenameField('vehicule', 'modele', 'modele_old'),

        # 2. Nouveaux champs FK
        migrations.AddField(
            model_name='vehicule',
            name='marque',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vehicules', to='parametrage.marquevehicule',
                verbose_name='Marque',
            ),
        ),
        migrations.AddField(
            model_name='vehicule',
            name='modele',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vehicules', to='parametrage.modelevehicule',
                verbose_name='Modèle',
            ),
        ),

        # 3. Conversion des données
        migrations.RunPython(convertir_donnees, reverse_donnees),

        # 4. Suppression des anciens champs
        migrations.RemoveField('vehicule', 'marque_old'),
        migrations.RemoveField('vehicule', 'modele_old'),
    ]

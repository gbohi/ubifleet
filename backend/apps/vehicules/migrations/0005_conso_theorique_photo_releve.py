"""Ajoute la consommation théorique d'origine du véhicule et la photo
du tableau de bord sur les relevés kilométriques."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('vehicules', '0004_marque_modele_fk')]

    operations = [
        migrations.AddField(
            model_name='vehicule',
            name='conso_theorique_origine',
            field=models.DecimalField(
                max_digits=5, decimal_places=2, default=0,
                help_text='Consommation constructeur ou de référence en L/100km',
                verbose_name="Consommation théorique à l'origine (L/100km)",
            ),
        ),
        migrations.AddField(
            model_name='relevekilometrage',
            name='photo_tableau_bord',
            field=models.ImageField(
                null=True, blank=True,
                upload_to='vehicules/releves/',
                verbose_name='Photo tableau de bord',
            ),
        ),
    ]

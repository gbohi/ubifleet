"""Migration : supprime unique=True et choices sur TypeDemande.code"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('demandes', '0002_types_initiaux')]

    operations = [
        migrations.AlterField(
            model_name='typedemande',
            name='code',
            field=models.CharField(
                max_length=50,
                help_text=(
                    "Code du formulaire : achat, vehicule, entretien, carburant, autre. "
                    "Plusieurs types peuvent partager le même code."
                )
            ),
        ),
    ]

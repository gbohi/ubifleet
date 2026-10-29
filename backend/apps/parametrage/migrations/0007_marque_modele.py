from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('parametrage', '0006_fix_prix_carburant_categorie')]

    operations = [
        migrations.CreateModel(
            name='MarqueVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('libelle', models.CharField(max_length=100, unique=True)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Marque véhicule',
                'verbose_name_plural': 'Marques véhicule',
                'ordering': ['libelle'],
            },
        ),
        migrations.CreateModel(
            name='ModeleVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('libelle', models.CharField(max_length=120)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('marque', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='modeles', to='parametrage.marquevehicule')),
            ],
            options={
                'verbose_name': 'Modèle véhicule',
                'verbose_name_plural': 'Modèles véhicule',
                'ordering': ['marque__libelle', 'libelle'],
                'unique_together': {('marque', 'libelle')},
            },
        ),
    ]

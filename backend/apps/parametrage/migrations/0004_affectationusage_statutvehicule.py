from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('parametrage', '0003_tournee')]

    operations = [
        migrations.CreateModel(
            name='AffectationUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('code',    models.CharField(max_length=20, unique=True)),
                ('libelle', models.CharField(max_length=100)),
                ('actif',   models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Affectation / Usage', 'ordering': ['code']},
        ),
        migrations.CreateModel(
            name='StatutVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('code',    models.CharField(max_length=30, unique=True)),
                ('libelle', models.CharField(max_length=100)),
                ('couleur', models.CharField(max_length=20, default='gray')),
                ('actif',   models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Statut véhicule', 'ordering': ['libelle']},
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('parametrage', '0002_seuils_etat_parc')]

    operations = [
        migrations.CreateModel(
            name='Tournee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name='ID')),
                ('code',         models.CharField(max_length=20, unique=True, verbose_name='Code')),
                ('libelle',      models.CharField(max_length=100, verbose_name='Libellé')),
                ('dotation',     models.PositiveIntegerField(default=0, verbose_name='Dotation (L)')),
                ('km_theorique', models.PositiveIntegerField(default=0, verbose_name='Km théorique')),
                ('actif',        models.BooleanField(default=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tournée',
                'verbose_name_plural': 'Tournées',
                'ordering': ['code'],
            },
        ),
    ]

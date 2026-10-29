from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('demandes', '0003_typeDemande_code_non_unique')]

    operations = [
        migrations.CreateModel(
            name='LigneDemandeAchat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name='ID')),
                ('designation', models.CharField(max_length=300, verbose_name='Désignation')),
                ('quantite', models.DecimalField(decimal_places=2, max_digits=10)),
                ('unite', models.CharField(blank=True, max_length=30)),
                ('prix_unitaire', models.DecimalField(blank=True, decimal_places=2,
                                                       max_digits=12, null=True,
                                                       verbose_name='Prix unitaire estimé (FCFA)')),
                ('fournisseur', models.CharField(blank=True, max_length=200)),
                ('notes', models.CharField(blank=True, max_length=300)),
                ('ordre', models.PositiveSmallIntegerField(default=0)),
                ('demande', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               related_name='lignes_achat',
                                               to='demandes.demande')),
            ],
            options={
                'verbose_name': "Ligne de demande d'achat",
                'verbose_name_plural': "Lignes de demande d'achat",
                'ordering': ['ordre', 'id'],
            },
        ),
    ]

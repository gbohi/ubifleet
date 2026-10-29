"""Rattache les tournées à une agence (champ obligatoire).

Les tournées existantes sont affectées à la première agence trouvée ;
elles devront être réaffectées manuellement depuis l'interface Paramètres.
"""
from django.db import migrations, models
import django.db.models.deletion


def assigner_agence_par_defaut(apps, schema_editor):
    Tournee = apps.get_model('parametrage', 'Tournee')
    Agence  = apps.get_model('accounts', 'Agence')

    sans_agence = Tournee.objects.filter(agence__isnull=True)
    if not sans_agence.exists():
        return

    agence = Agence.objects.order_by('code').first()
    if agence is None:
        # Aucune agence en base : on en crée une technique pour satisfaire
        # la contrainte, à corriger depuis l'interface.
        agence = Agence.objects.create(
            nom='Agence à définir', code='TMP', ville='',
        )
    sans_agence.update(agence=agence)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('parametrage', '0007_marque_modele'),
        ('accounts',    '__first__'),
    ]

    operations = [
        migrations.AddField(
            model_name='tournee',
            name='agence',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='tournees', to='accounts.agence',
                verbose_name='Agence',
            ),
        ),
        migrations.RunPython(assigner_agence_par_defaut, noop),
        migrations.AlterField(
            model_name='tournee',
            name='agence',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='tournees', to='accounts.agence',
                verbose_name='Agence',
            ),
        ),
    ]

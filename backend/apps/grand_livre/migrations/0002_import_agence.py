from django.db import migrations, models


def renseigner_agence(apps, schema_editor):
    ImportGrandLivre = apps.get_model('grand_livre', 'ImportGrandLivre')
    LigneGrandLivre = apps.get_model('grand_livre', 'LigneGrandLivre')
    for imp in ImportGrandLivre.objects.filter(code_agence=''):
        ligne = LigneGrandLivre.objects.filter(import_source=imp).first()
        if ligne:
            imp.code_agence = ligne.code_agence
            imp.libelle_agence = ligne.libelle_agence
            imp.save(update_fields=['code_agence', 'libelle_agence'])


class Migration(migrations.Migration):
    dependencies = [('grand_livre', '0001_squashed')]

    operations = [
        migrations.AddField(
            model_name='importgrandlivre', name='code_agence',
            field=models.CharField(blank=True, db_index=True, max_length=20, verbose_name='Code agence'),
        ),
        migrations.AddField(
            model_name='importgrandlivre', name='libelle_agence',
            field=models.CharField(blank=True, max_length=200, verbose_name='Libellé agence'),
        ),
        migrations.RunPython(renseigner_agence, migrations.RunPython.noop),
    ]

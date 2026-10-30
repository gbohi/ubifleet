"""La tournée d'un relevé kilométrique devient une référence au référentiel
Tournée (elle était saisie en texte libre).

Un texte est rattaché à la tournée dont le code ou le libellé correspond, pour
les relevés de type « tournée ». Sinon (texte inconnu, ou destination saisie
sur un autre type de mouvement) il est conservé dans les notes du relevé.
"""

from django.db import migrations, models
import django.db.models.deletion


def rattacher(apps, schema_editor):
    Releve = apps.get_model('vehicules', 'ReleveKilometrage')
    Tournee = apps.get_model('parametrage', 'Tournee')
    index = {}
    for t in Tournee.objects.all():
        for cle in (t.code, t.libelle, f'{t.code} — {t.libelle}', f'{t.code} - {t.libelle}'):
            index.setdefault(cle.strip().lower(), t.pk)
    for r in Releve.objects.exclude(tournee_texte__isnull=True).exclude(tournee_texte=''):
        texte = r.tournee_texte.strip()
        tournee_id = index.get(texte.lower()) if r.type_mouvement == 'tournee' else None
        if tournee_id:
            r.tournee_id = tournee_id
        else:
            note = f'Tournée / destination : {texte}'
            r.notes = f'{r.notes}\n{note}' if r.notes else note
        r.save(update_fields=['tournee', 'notes'])


def detacher(apps, schema_editor):
    Releve = apps.get_model('vehicules', 'ReleveKilometrage')
    for r in Releve.objects.filter(tournee__isnull=False).select_related('tournee'):
        r.tournee_texte = r.tournee.libelle
        r.save(update_fields=['tournee_texte'])


class Migration(migrations.Migration):

    dependencies = [
        ('vehicules', '0005_heure_releve'),
        ('parametrage', '0006_type_tournee_reserve'),
    ]

    operations = [
        migrations.RenameField('relevekilometrage', 'tournee', 'tournee_texte'),
        migrations.AddField(
            model_name='relevekilometrage',
            name='tournee',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='releves_kilometrage', to='parametrage.tournee', verbose_name='Tournée'),
        ),
        migrations.RunPython(rattacher, detacher),
        migrations.RemoveField(model_name='relevekilometrage', name='tournee_texte'),
    ]

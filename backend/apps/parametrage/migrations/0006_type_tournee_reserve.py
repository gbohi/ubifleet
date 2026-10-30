"""Le type de mouvement « tournee » devient réservé (il demande la tournée) :
on le recrée s'il a été supprimé, et l'option « avec tournée » disparaît."""

from django.db import migrations


def assurer_type_tournee(apps, schema_editor):
    TypeMouvement = apps.get_model('parametrage', 'TypeMouvement')
    TypeMouvement.objects.get_or_create(
        code='tournee', defaults={'libelle': 'Tournée', 'couleur': 'blue', 'ordre': 4, 'actif': True})


class Migration(migrations.Migration):

    dependencies = [
        ('parametrage', '0005_corrections_saisie'),
    ]

    operations = [
        migrations.RunPython(assurer_type_tournee, migrations.RunPython.noop),
        migrations.RemoveField(model_name='typemouvement', name='avec_tournee'),
    ]

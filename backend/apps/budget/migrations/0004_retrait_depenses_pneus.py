"""Le coût d'un changement de pneus est compté par son intervention : les
dépenses reportées depuis le suivi des pneus sont retirées (évite le double compte)."""

from django.db import migrations


def retirer(apps, schema_editor):
    apps.get_model('budget', 'DepenseVehicule').objects.filter(ref_objet_type='pneu').delete()


class Migration(migrations.Migration):

    dependencies = [('budget', '0003_depenses_automatiques')]

    operations = [migrations.RunPython(retirer, migrations.RunPython.noop)]

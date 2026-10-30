# Kilométrage d'entrée dans le parc : plancher du compteur recalculé à partir des saisies.

from django.db import migrations, models
from django.db.models import Max, Min


def initialiser(apps, schema_editor):
    """Kilométrage d'entrée = plus petit kilométrage connu du véhicule.
    Si le compteur dépasse toutes les saisies (mis à jour depuis la fiche
    véhicule), il est historisé par un relevé pour ne pas être perdu au
    prochain recalcul."""
    Vehicule = apps.get_model('vehicules', 'Vehicule')
    Releve = apps.get_model('vehicules', 'ReleveKilometrage')
    Plein = apps.get_model('carburant', 'PleinsCarburant')
    for v in Vehicule.objects.all():
        r = Releve.objects.filter(vehicule=v).aggregate(mn=Min('kilometrage'), mx=Max('kilometrage'))
        p = Plein.objects.filter(vehicule=v).aggregate(mn=Min('kilometrage_releve'), mx=Max('kilometrage_releve'))
        mins = [x for x in (r['mn'], p['mn']) if x is not None]
        maxs = [x for x in (r['mx'], p['mx']) if x is not None]
        if not maxs:
            v.kilometrage_initial = v.kilometrage_actuel
        else:
            v.kilometrage_initial = min(mins + [v.kilometrage_actuel])
            if v.kilometrage_actuel > max(maxs):
                Releve.objects.create(
                    vehicule=v, kilometrage=v.kilometrage_actuel, type_mouvement='releve',
                    date_releve=(v.updated_at or v.created_at).date(),
                    notes='Reprise du kilométrage de la fiche véhicule.',
                )
        v.save(update_fields=['kilometrage_initial'])


class Migration(migrations.Migration):

    dependencies = [
        ("vehicules", "0003_fenetre_saisie"),
        ("carburant", "0003_fenetre_saisie"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="kilometrage_initial",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Kilométrage à l'entrée dans le parc"
            ),
        ),
        migrations.RunPython(initialiser, migrations.RunPython.noop),
    ]

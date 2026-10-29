from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('carburant', '0002_pleinscarburant_tournee')]

    operations = [
        migrations.AddField(
            model_name='pleinscarburant',
            name='kilometrage_depart',
            field=models.PositiveIntegerField(
                null=True, blank=True,
                verbose_name='Kilométrage départ (km du plein précédent)'
            ),
        ),
    ]

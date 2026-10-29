from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('carburant', '0001_initial'),
        ('parametrage', '0003_tournee'),
    ]

    operations = [
        migrations.AddField(
            model_name='pleinscarburant',
            name='tournee',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pleins',
                to='parametrage.tournee',
                verbose_name='Tournée'
            ),
        ),
    ]

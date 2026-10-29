"""Documents attachés aux interventions (planification et clôture)."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('entretien', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='DocumentIntervention',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('fichier', models.FileField(upload_to='entretien/documents/')),
                ('nom', models.CharField(blank=True, max_length=255)),
                ('type_doc', models.CharField(
                    choices=[('planification', 'Document de planification'),
                             ('cloture', 'Rapport de clôture'),
                             ('autre', 'Autre document')],
                    default='autre', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('intervention', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='documents', to='entretien.intervention')),
            ],
            options={
                'verbose_name': 'Document intervention',
                'verbose_name_plural': 'Documents intervention',
                'ordering': ['-created_at'],
            },
        ),
    ]

"""Types de véhicule paramétrables : la liste fixe devient un référentiel
(les véhicules gardent leur code)."""

from django.db import migrations, models

TYPES = [
    ('berline', 'Berline', 1), ('suv', 'SUV / 4×4', 2), ('minibus', 'Minibus', 3),
    ('camionnette', 'Camionnette / Fourgonnette', 4), ('pickup', 'Pick-up', 5),
    ('camion', 'Camion', 6), ('moto', 'Moto', 7),
]


def initialiser(apps, schema_editor):
    TypeVehicule = apps.get_model('parametrage', 'TypeVehicule')
    Vehicule = apps.get_model('vehicules', 'Vehicule')
    for code, libelle, ordre in TYPES:
        TypeVehicule.objects.get_or_create(code=code, defaults={'libelle': libelle, 'ordre': ordre})
    # Codes présents sur des véhicules sans type correspondant
    for code in Vehicule.objects.exclude(type_vehicule__in=[t[0] for t in TYPES]) \
            .values_list('type_vehicule', flat=True).distinct():
        if code:
            TypeVehicule.objects.get_or_create(code=code, defaults={'libelle': code.capitalize(), 'ordre': 99})


class Migration(migrations.Migration):

    dependencies = [
        ('parametrage', '0007_types_mouvement_prises'),
        ('vehicules', '0008_carte_carburant'),
    ]

    operations = [
        migrations.CreateModel(
            name='TypeVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(help_text='Identifiant technique, enregistré sur les véhicules.', max_length=20, unique=True)),
                ('libelle', models.CharField(max_length=100)),
                ('ordre', models.PositiveSmallIntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Type de véhicule', 'verbose_name_plural': 'Types de véhicule',
                     'ordering': ['ordre', 'libelle']},
        ),
        migrations.RunPython(initialiser, migrations.RunPython.noop),
    ]

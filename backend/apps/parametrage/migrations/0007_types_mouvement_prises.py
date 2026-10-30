"""Types de mouvement communs aux relevés et aux prises de carburant :
chaque type indique à quelles saisies il s'applique. Le type « tournée »
sert aux deux ; Course, Ramassage et Mission sont créés pour les prises."""

from django.db import migrations, models

TYPES_PRISES = [
    # code, libellé, couleur, ordre
    ('course',    'Course',    'orange', 10),
    ('ramassage', 'Ramassage', 'green',  11),
    ('mission',   'Mission',   'red',    12),
]


def initialiser(apps, schema_editor):
    TypeMouvement = apps.get_model('parametrage', 'TypeMouvement')
    TypeMouvement.objects.filter(code='tournee').update(pour_releves=True, pour_prises=True)
    for code, libelle, couleur, ordre in TYPES_PRISES:
        TypeMouvement.objects.get_or_create(code=code, defaults={
            'libelle': libelle, 'couleur': couleur, 'ordre': ordre, 'actif': True,
            'pour_releves': False, 'pour_prises': True,
        })


class Migration(migrations.Migration):

    dependencies = [
        ('parametrage', '0006_type_tournee_reserve'),
    ]

    operations = [
        migrations.AddField(
            model_name='typemouvement', name='pour_releves',
            field=models.BooleanField(default=True, verbose_name='Relevés kilométriques'),
        ),
        migrations.AddField(
            model_name='typemouvement', name='pour_prises',
            field=models.BooleanField(default=False, verbose_name='Prises de carburant'),
        ),
        migrations.RunPython(initialiser, migrations.RunPython.noop),
    ]

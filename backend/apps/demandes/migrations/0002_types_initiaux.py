"""Données initiales — types de demandes et niveaux de validation."""
from django.db import migrations

TYPES = [
    {'code': 'vehicule',  'nom': 'Demande de véhicule / mission',     'nb_niveaux': 2},
    {'code': 'entretien', 'nom': "Demande d'entretien / réparation",  'nb_niveaux': 2},
    {'code': 'carburant', 'nom': 'Demande de carburant',              'nb_niveaux': 1},
    {'code': 'achat',     'nom': "Demande d'achat de matériel",       'nb_niveaux': 3},
    {'code': 'autre',     'nom': 'Autre demande',                     'nb_niveaux': 2},
]

NIVEAUX = {
    'vehicule':  [{'niveau': 1, 'libelle': 'Chef de service'},
                  {'niveau': 2, 'libelle': 'Responsable flotte'}],
    'entretien': [{'niveau': 1, 'libelle': 'Chef de service'},
                  {'niveau': 2, 'libelle': 'Responsable flotte'}],
    'carburant': [{'niveau': 1, 'libelle': 'Responsable flotte'}],
    'achat':     [{'niveau': 1, 'libelle': 'Chef de service'},
                  {'niveau': 2, 'libelle': 'Responsable flotte'},
                  {'niveau': 3, 'libelle': 'Direction Générale'}],
    'autre':     [{'niveau': 1, 'libelle': 'Chef de service'},
                  {'niveau': 2, 'libelle': 'Responsable flotte'}],
}


def insert_types(apps, schema_editor):
    TypeDemande      = apps.get_model('demandes', 'TypeDemande')
    NiveauValidation = apps.get_model('demandes', 'NiveauValidation')
    for t in TYPES:
        td, _ = TypeDemande.objects.get_or_create(code=t['code'], defaults={
            'nom': t['nom'], 'nb_niveaux': t['nb_niveaux'], 'actif': True,
        })
        for n in NIVEAUX.get(t['code'], []):
            NiveauValidation.objects.get_or_create(
                type_demande=td, niveau=n['niveau'],
                defaults={'libelle': n['libelle']}
            )


def delete_types(apps, schema_editor):
    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    TypeDemande.objects.filter(code__in=[t['code'] for t in TYPES]).delete()


class Migration(migrations.Migration):
    dependencies = [('demandes', '0001_initial')]
    operations   = [migrations.RunPython(insert_types, delete_types)]

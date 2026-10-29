"""Données initiales — éléments de contrôle véhicule."""
from django.db import migrations

ELEMENTS = [
    # Moteur
    ('moteur', 'Niveau huile moteur',        1, True),
    ('moteur', 'Niveau liquide refroidissement', 2, True),
    ('moteur', 'Niveau liquide frein',       3, True),
    ('moteur', 'Courroie / ventilateur',     4, False),
    ('moteur', 'Fuites (huile, eau, carburant)', 5, True),
    # Sécurité
    ('securite', 'Freins (efficacité)',       1, True),
    ('securite', 'Frein à main',              2, True),
    ('securite', 'Ceintures de sécurité',     3, True),
    ('securite', 'Klaxon',                    4, False),
    ('securite', 'Airbags (témoins tableau)', 5, False),
    # Carrosserie
    ('carrosserie', 'Pare-brise (fissures)',  1, True),
    ('carrosserie', 'Rétroviseurs',           2, True),
    ('carrosserie', 'Portes (fermeture)',      3, False),
    ('carrosserie', 'Dégâts / rayures',       4, False),
    # Éclairage
    ('eclairage', 'Feux avant',               1, True),
    ('eclairage', 'Feux arrière',             2, True),
    ('eclairage', 'Clignotants',              3, True),
    ('eclairage', 'Feux de recul',            4, False),
    ('eclairage', 'Feux de détresse',         5, True),
    # Pneumatiques
    ('pneumatiques', 'Pression pneus AV',     1, True),
    ('pneumatiques', 'Pression pneus AR',     2, True),
    ('pneumatiques', 'Usure pneus AV',        3, True),
    ('pneumatiques', 'Usure pneus AR',        4, True),
    ('pneumatiques', 'Roue de secours',       5, False),
    # Intérieur
    ('interieur', 'Propreté habitacle',       1, False),
    ('interieur', 'Tableau de bord (témoins)',2, True),
    ('interieur', 'Climatisation',            3, False),
    ('interieur', 'Extincteur',               4, True),
    ('interieur', 'Triangle de présignalisation', 5, True),
    # Administratif
    ('administratif', 'Carte grise',          1, True),
    ('administratif', 'Assurance',            2, True),
    ('administratif', 'Contrôle technique',   3, True),
    ('administratif', 'Carte de transport',   4, False),
]


def insert_elements(apps, schema_editor):
    ElementControle = apps.get_model('controle', 'ElementControle')
    for cat, nom, ordre, oblig in ELEMENTS:
        ElementControle.objects.get_or_create(
            nom=nom, categorie=cat,
            defaults={'ordre': ordre, 'obligatoire': oblig, 'actif': True}
        )


def delete_elements(apps, schema_editor):
    ElementControle = apps.get_model('controle', 'ElementControle')
    ElementControle.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('controle', '0001_initial')]
    operations   = [migrations.RunPython(insert_elements, delete_elements)]

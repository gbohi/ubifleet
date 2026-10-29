"""Données initiales : paramètres, affectations, statuts véhicule."""
from django.db import migrations

PARAMETRES = [
    ('alerte_permis_jours',    '60',  'alertes', 'Nb jours avant expiration permis'),
    ('alerte_assurance_jours', '30',  'alertes', 'Nb jours avant expiration assurance'),
    ('alerte_ct_jours',        '30',  'alertes', 'Nb jours avant expiration CT'),
    ('conso_seuil_pct',        '30',  'alertes', 'Seuil anomalie consommation (%)'),
    ('revision_km_urgent',     '500', 'alertes', 'Km restants avant révision urgente'),
    ('devise',                 'FCFA','general',  'Devise'),
    ('prix_carburant_litre',    '700', 'alertes', 'Prix par défaut du litre de carburant (FCFA)'),
    ('km_max_par_jour',        '800', 'general',  'Km max par jour (seuil alerte)'),
]

AFFECTATIONS = [
    ('DIRECTION',    'Véhicule de direction'),
    ('COMMERCIAL',   'Véhicule commercial'),
    ('LIVRAISON',    'Livraison'),
    ('TOURNEE',      'Tournée'),
    ('POOL',         'Véhicule de pool'),
    ('MAINTENANCE',  'Maintenance / Technique'),
    ('AUTRE',        'Autre usage'),
]

STATUTS = [
    ('en_service',  'En service',                  'green'),
    ('en_revision', 'En révision',                 'orange'),
    ('en_panne',    'En panne',                    'red'),
    ('immobilise',  'Immobilisé',                  'red'),
    ('vendu',       'Vendu / Réformé',             'gray'),
    ('accidente',   'Accidenté',                   'red'),
    ('en_attente',  'En attente mise en service',  'blue'),
]


def insert_data(apps, schema_editor):
    Parametre        = apps.get_model('parametrage', 'Parametre')
    AffectationUsage = apps.get_model('parametrage', 'AffectationUsage')
    StatutVehicule   = apps.get_model('parametrage', 'StatutVehicule')

    for cle, valeur, categorie, description in PARAMETRES:
        Parametre.objects.get_or_create(
            cle=cle,
            defaults={'valeur': valeur, 'categorie': categorie, 'description': description}
        )
    for code, libelle in AFFECTATIONS:
        AffectationUsage.objects.get_or_create(code=code, defaults={'libelle': libelle})
    for code, libelle, couleur in STATUTS:
        StatutVehicule.objects.get_or_create(
            code=code, defaults={'libelle': libelle, 'couleur': couleur}
        )


def delete_data(apps, schema_editor):
    apps.get_model('parametrage', 'Parametre').objects.all().delete()
    apps.get_model('parametrage', 'AffectationUsage').objects.all().delete()
    apps.get_model('parametrage', 'StatutVehicule').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('parametrage', '0001_initial')]
    operations   = [migrations.RunPython(insert_data, delete_data)]

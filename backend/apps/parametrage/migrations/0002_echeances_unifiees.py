"""Échéances unifiées : un couple de seuils (attention / urgent) par échéance,
utilisé à la fois par l'État du parc et par les alertes.

Les valeurs actuelles sont reprises :
- documents (assurance, CT, carte de transport, vignette) ← seuils jours de l'État du parc
  (ce sont eux qui pilotaient déjà les alertes documents) ;
- permis : attention ← alerte_permis_jours ; urgent : 15 jours ;
- révision et pneus ← seuils km de l'État du parc ;
- consommation anormale ← conso_seuil_pct / alerte_conso_seuil_pct.
Les anciennes clés, dont certaines n'avaient aucun effet, sont supprimées.
"""
from django.db import migrations

DOCUMENTS = ['assurance', 'ct', 'carte_transport', 'vignette']
LIBELLES = {
    'assurance': 'Assurance', 'ct': 'Contrôle technique',
    'carte_transport': 'Carte de transport', 'vignette': 'Vignette',
    'permis': 'Permis de conduire', 'revision': 'Révision', 'pneus': 'Pneus',
}
ANCIENNES_CLES = [
    'alerte_permis_jours', 'alerte_assurance_jours', 'alerte_ct_jours',
    'conso_seuil_pct', 'alerte_conso_seuil_pct', 'revision_km_urgent',
    'etat_parc_km_urgent', 'etat_parc_km_attention',
    'etat_parc_jours_urgent', 'etat_parc_jours_attention',
]


def _lire(Parametre, cle, defaut):
    p = Parametre.objects.filter(cle=cle).first()
    try:
        return int(float(p.valeur)) if p else defaut
    except (TypeError, ValueError):
        return defaut


def _ecrire(Parametre, cle, valeur, description):
    Parametre.objects.update_or_create(cle=cle, defaults={
        'valeur': str(valeur), 'type_valeur': 'int',
        'categorie': 'alertes', 'description': description,
    })


def unifier(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    jours_att = _lire(Parametre, 'etat_parc_jours_attention', 30)
    jours_urg = _lire(Parametre, 'etat_parc_jours_urgent', 7)
    km_att = _lire(Parametre, 'etat_parc_km_attention', 2000)
    km_urg = _lire(Parametre, 'etat_parc_km_urgent', 500)
    permis_att = _lire(Parametre, 'alerte_permis_jours', 60)

    valeurs = {code: (jours_att, jours_urg) for code in DOCUMENTS}
    valeurs['permis'] = (permis_att, min(15, max(permis_att - 1, 1)))
    valeurs['revision'] = (km_att, km_urg)
    valeurs['pneus'] = (km_att, km_urg)

    for code, (attention, urgent) in valeurs.items():
        unite = 'km' if code in ('revision', 'pneus') else 'jours'
        _ecrire(Parametre, f'echeance_{code}_attention', attention,
                f'{LIBELLES[code]} — seuil attention ({unite} restants)')
        _ecrire(Parametre, f'echeance_{code}_urgent', urgent,
                f'{LIBELLES[code]} — seuil urgent ({unite} restants)')

    conso = _lire(Parametre, 'alerte_conso_seuil_pct', _lire(Parametre, 'conso_seuil_pct', 30))
    _ecrire(Parametre, 'conso_anomalie_pct', conso,
            "Consommation anormale — % au-dessus de la moyenne du véhicule")

    Parametre.objects.filter(cle__in=ANCIENNES_CLES).delete()


def revenir(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    anciennes = {
        'etat_parc_jours_attention': _lire(Parametre, 'echeance_assurance_attention', 30),
        'etat_parc_jours_urgent': _lire(Parametre, 'echeance_assurance_urgent', 7),
        'etat_parc_km_attention': _lire(Parametre, 'echeance_revision_attention', 2000),
        'etat_parc_km_urgent': _lire(Parametre, 'echeance_revision_urgent', 500),
        'alerte_permis_jours': _lire(Parametre, 'echeance_permis_attention', 60),
        'conso_seuil_pct': _lire(Parametre, 'conso_anomalie_pct', 30),
    }
    for cle, valeur in anciennes.items():
        _ecrire(Parametre, cle, valeur, cle)
    Parametre.objects.filter(cle__startswith='echeance_').delete()
    Parametre.objects.filter(cle='conso_anomalie_pct').delete()


class Migration(migrations.Migration):
    dependencies = [('parametrage', '0001_squashed')]
    operations = [migrations.RunPython(unifier, revenir)]

"""Reprise des prises saisies avant les tournées effectuées.

Prises avec une tournée → type « tournee », regroupées en tournées
effectuées : prises consécutives d'un même véhicule pour la même tournée,
sans autre prise entre elles. Ces tournées sont clôturées (KM retour = km
de la dernière prise) et marquées « à vérifier ». Prises sans tournée →
type « course »."""

from datetime import datetime, time, timezone as dt_timezone

from django.db import migrations


def _cle(p):
    return (p.date_plein, p.heure_plein is None, p.heure_plein or time.min,
            p.created_at or datetime.max.replace(tzinfo=dt_timezone.utc))


def reprendre(apps, schema_editor):
    Prise = apps.get_model('carburant', 'PleinsCarburant')
    TE = apps.get_model('carburant', 'TourneeEffectuee')
    Changement = apps.get_model('parametrage', 'ChangementDotation')

    Prise.objects.filter(tournee__isnull=True).update(type_mouvement='course')
    Prise.objects.filter(tournee__isnull=False).update(type_mouvement='tournee')

    def dotation_au(tournee, d):
        valeur = None
        for c in Changement.objects.filter(tournee=tournee, statut__in=['initiale', 'approuvee']).order_by('created_at'):
            if (c.date_decision or c.created_at).date() <= d:
                valeur = c.nouvelle_dotation
        return valeur if valeur is not None else tournee.dotation

    compteurs = {}

    def creer(groupe):
        t, premiere, derniere = groupe[0].tournee, groupe[0], groupe[-1]
        prefixe = f"{t.code}-{premiere.date_plein.year}-"
        n = compteurs.get(prefixe, 0) + 1
        compteurs[prefixe] = n
        te = TE.objects.create(
            numero=f"{prefixe}{n:04d}", tournee=t, vehicule_id=premiere.vehicule_id,
            chauffeur_id=premiere.chauffeur_id, agence_id=premiere.agence_id, statut='cloturee',
            date_debut=premiere.date_plein, heure_debut=premiere.heure_plein, km_depart=premiere.kilometrage_releve,
            date_fin=derniere.date_plein, heure_fin=derniere.heure_plein, km_retour=derniere.kilometrage_releve,
            dotation_theorique=dotation_au(t, premiere.date_plein), km_theorique=t.km_theorique or 0,
            a_verifier=True,
        )
        Prise.objects.filter(pk__in=[p.pk for p in groupe]).update(tournee_effectuee=te)

    vehicules = Prise.objects.order_by().values_list('vehicule_id', flat=True).distinct()
    for vid in vehicules:
        prises = sorted(Prise.objects.filter(vehicule_id=vid).select_related('tournee'), key=_cle)
        groupe = []
        for p in prises:
            if groupe and (p.tournee_id is None or p.tournee_id != groupe[0].tournee_id):
                creer(groupe)
                groupe = []
            if p.tournee_id is not None:
                groupe.append(p)
        if groupe:
            creer(groupe)


def annuler(apps, schema_editor):
    apps.get_model('carburant', 'TourneeEffectuee').objects.filter(a_verifier=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('carburant', '0006_tournees_effectuees'),
        ('parametrage', '0007_types_mouvement_prises'),
    ]

    operations = [
        migrations.RunPython(reprendre, annuler),
    ]

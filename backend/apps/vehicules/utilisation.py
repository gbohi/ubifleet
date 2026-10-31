"""UbiFleet — Utilisation du parc (onglet des relevés kilométriques).

Compteur d'un véhicule = ses saisies kilométriques (relevés et prises de
carburant). Sur une période, par véhicule : km parcourus (compteur estimé en
début et en fin de période), jours d'utilisation (jours où le compteur
avance), dernière saisie et jours sans saisie, sauts suspects (plus de N km
par jour écoulé entre deux saisies), révision (km restants, date estimée au
rythme de la période). Seuils : Paramètres › Seuils.
"""

from datetime import date, datetime, time as dtime, timedelta

from apps.carburant.analyses import compteur_a

CLE_JOURS_SANS_SAISIE, JOURS_SANS_SAISIE_DEFAUT = 'utilisation_jours_sans_saisie', 7
CLE_SAUT_KM_JOUR, SAUT_KM_JOUR_DEFAUT = 'utilisation_saut_km_jour', 800


def seuils():
    from apps.parametrage.models import Parametre
    return (int(float(Parametre.get(CLE_JOURS_SANS_SAISIE, JOURS_SANS_SAISIE_DEFAUT))),
            int(float(Parametre.get(CLE_SAUT_KM_JOUR, SAUT_KM_JOUR_DEFAUT))))


def saisies_des_vehicules(ids, jusqua):
    """{vehicule_id: [(datetime, km, source)]} triées, jusqu'à la date donnée."""
    from apps.carburant.models import PleinsCarburant
    from apps.vehicules.models import ReleveKilometrage
    saisies = {}
    for vid, d, h, km in ReleveKilometrage.objects.filter(vehicule_id__in=ids, date_releve__lte=jusqua) \
            .values_list('vehicule_id', 'date_releve', 'heure_releve', 'kilometrage'):
        saisies.setdefault(vid, []).append((datetime.combine(d, h or dtime(12, 0)), km, 'relevé'))
    for vid, d, h, km in PleinsCarburant.objects.filter(vehicule_id__in=ids, date_plein__lte=jusqua) \
            .values_list('vehicule_id', 'date_plein', 'heure_plein', 'kilometrage_releve'):
        saisies.setdefault(vid, []).append((datetime.combine(d, h or dtime(12, 0)), km, 'prise de carburant'))
    for liste in saisies.values():
        liste.sort(key=lambda s: s[0])
    return saisies


def _r(x, n=0):
    return round(x, n) if x is not None else None


def utilisation(vehicules, saisies, debut, fin, aujourdhui=None, depenses=None):
    """`depenses` : {vehicule_id: {'total': FCFA, 'carburant': FCFA}} sur la période."""
    depenses = depenses or {}
    aujourdhui = aujourdhui or date.today()
    jours_max, saut_km_jour = seuils()
    debut_dt, fin_dt = datetime.combine(debut, dtime.min), datetime.combine(fin, dtime.max)
    nb_jours_periode = (fin - debut).days + 1
    reference = min(fin, aujourdhui)
    lignes = []
    for v in vehicules:
        liste = saisies.get(v.pk, [])
        couple = [(q, km) for q, km, _ in liste]
        km_debut = compteur_a(couple, debut_dt) if couple else None
        km_fin = compteur_a(couple, fin_dt) if couple else None
        km = km_fin - km_debut if km_debut is not None and km_fin is not None else None
        if km is not None:
            km = max(km, 0)

        dans = [s for s in liste if debut_dt <= s[0] <= fin_dt]
        jours, sauts, precedente = set(), [], None
        for s in liste:
            if precedente and s[1] > precedente[1] and debut_dt <= s[0] <= fin_dt:
                jours.add(s[0].date())
                ecoule = max((s[0] - precedente[0]).total_seconds() / 86400, 1)
                par_jour = (s[1] - precedente[1]) / ecoule
                if par_jour > saut_km_jour:
                    sauts.append({
                        'du': precedente[0].isoformat(), 'au': s[0].isoformat(),
                        'km_avant': precedente[1], 'km_apres': s[1], 'km': s[1] - precedente[1],
                        'km_par_jour': _r(par_jour), 'source': s[2],
                    })
            precedente = s
        jusqua_fin = [s for s in liste if s[0] <= fin_dt]
        derniere = jusqua_fin[-1] if jusqua_fin else None
        jours_sans = (reference - derniere[0].date()).days if derniere else None

        restant = (v.kilometrage_revision - v.kilometrage_actuel) if v.kilometrage_revision else None
        rythme = km / nb_jours_periode if km else None        # km par jour calendaire
        date_revision = None
        if restant is not None and restant > 0 and rythme:
            date_revision = (aujourdhui + timedelta(days=int(restant / rythme))).isoformat()
        lignes.append({
            'vehicule_id': str(v.pk), 'immatriculation': v.immatriculation,
            'marque': v.marque_str, 'modele': v.modele_str, 'agence_nom': v.agence.nom if v.agence else None,
            'statut': v.statut.libelle if getattr(v, 'statut', None) else None,
            'km_debut': _r(km_debut), 'km_fin': _r(km_fin), 'km_parcourus': _r(km),
            'jours_utilisation': len(jours), 'nb_jours_periode': nb_jours_periode,
            'km_par_jour_roule': _r(km / len(jours)) if km and jours else None,
            'nb_saisies': len(dans),
            'derniere_saisie': derniere[0].isoformat() if derniere else None,
            'derniere_saisie_km': derniere[1] if derniere else None,
            'jours_sans_saisie': jours_sans,
            'sans_saisie_recente': jours_sans is None or jours_sans > jours_max,
            'sauts': sauts, 'nb_sauts': len(sauts),
            'km_revision': v.kilometrage_revision or None, 'km_avant_revision': restant,
            'date_revision_estimee': date_revision,
            'depenses': _r(depenses.get(v.pk, {}).get('total')),
            'cout_km': _r(depenses[v.pk]['total'] / km, 1) if km and depenses.get(v.pk, {}).get('total') else None,
            'cout_carburant_km': _r(depenses[v.pk]['carburant'] / km, 1)
                                 if km and depenses.get(v.pk, {}).get('carburant') else None,
        })
    lignes.sort(key=lambda l: (-(l['nb_sauts']), not l['sans_saisie_recente'], -(l['km_parcourus'] or 0)))
    actifs = [l for l in lignes if l['km_parcourus']]
    # Coût au km par agence (véhicules ayant roulé)
    par_agence = {}
    for l in actifs:
        a = par_agence.setdefault(l['agence_nom'] or '—', {'agence': l['agence_nom'] or '—', 'km': 0, 'depenses': 0})
        a['km'] += l['km_parcourus']
        a['depenses'] += l['depenses'] or 0
    for a in par_agence.values():
        a['cout_km'] = _r(a['depenses'] / a['km'], 1) if a['km'] and a['depenses'] else None
    return {
        'resultats': lignes,
        'synthese': {
            'nb_vehicules': len(lignes), 'km_total': sum(l['km_parcourus'] or 0 for l in lignes),
            'nb_actifs': len(actifs), 'nb_inactifs': len(lignes) - len(actifs),
            'nb_sans_saisie_recente': sum(1 for l in lignes if l['sans_saisie_recente']),
            'nb_sauts': sum(l['nb_sauts'] for l in lignes),
            'nb_revision_depassee': sum(1 for l in lignes if (l['km_avant_revision'] or 1) <= 0),
            'cout_km_parc': _r(sum(a['depenses'] for a in par_agence.values())
                               / sum(a['km'] for a in par_agence.values()), 1)
                            if sum(a['km'] for a in par_agence.values()) and sum(a['depenses'] for a in par_agence.values()) else None,
        },
        'par_agence': sorted(par_agence.values(), key=lambda a: a['agence']),
        'seuils': {'jours_sans_saisie': jours_max, 'saut_km_jour': saut_km_jour},
    }

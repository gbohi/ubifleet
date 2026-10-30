"""UbiFleet — Analyses carburant : consommation par véhicule, évolution
mensuelle par agence, rapprochement avec les transactions TotalEnergies.

Consommation (méthode « plein à plein », la même que les anomalies) : chaque
prise couvre les km parcourus depuis la prise précédente du véhicule
(kilometrage_releve − kilometrage_depart). Conso = Σ litres ÷ Σ km × 100 sur
les prises retenues ; un filtre (chauffeur, type de mouvement) ne garde que
les intervalles de ses prises, sans mélanger ceux des autres.

Rapprochement Total : transactions effectives (ventes non annulées) associées
au véhicule par sa carte carburant, sinon par la plaque normalisée ; chaque
transaction est appariée à la prise la plus proche (même véhicule, écart
d'heure toléré, volume proche) ; restent les transactions sans prise et les
prises sans transaction.
"""

import re
from collections import defaultdict
from datetime import date, datetime, time as dtime, timedelta

from .anomalies import ordre_chronologique

CLE_TOLERANCE_HEURES, TOLERANCE_HEURES_DEFAUT = 'rapprochement_tolerance_heures', 6
CLE_ECART_PCT, ECART_PCT_DEFAUT = 'rapprochement_ecart_pct', 5


def _r(x, n=2):
    return round(x, n) if x is not None else None


def normaliser_immat(valeur):
    """Plaque comparable : majuscules et chiffres seuls, sans suffixe pays
    (« 56317WW-CI », « 56317 WW CI » et « 56317 WW 01 » → « 56317WW »)."""
    s = re.sub(r'[^A-Z0-9]', '', (valeur or '').upper())
    for suffixe in ('CI', '01'):
        if len(s) > 5 and s.endswith(suffixe):
            s = s[:-len(suffixe)]
    return s


def normaliser_carte(valeur):
    return re.sub(r'\D', '', valeur or '')


def mois_entre(debut, fin):
    m, fin_m = date(debut.year, debut.month, 1), date(fin.year, fin.month, 1)
    out = []
    while m <= fin_m:
        out.append(m.strftime('%Y-%m'))
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    return out


def _km(p):
    if p.kilometrage_depart is not None and p.kilometrage_releve > p.kilometrage_depart:
        return p.kilometrage_releve - p.kilometrage_depart
    return None


# ── Consommation par véhicule ─────────────────────────────────────────

def consommation_vehicules(prises):
    """Une ligne par véhicule ayant au moins une prise parmi `prises`."""
    par_vehicule = defaultdict(list)
    for p in prises:
        par_vehicule[p.vehicule_id].append(p)
    lignes = []
    for liste in par_vehicule.values():
        liste.sort(key=ordre_chronologique)
        v = liste[0].vehicule
        litres = sum(float(p.volume_litres) for p in liste)
        montant = sum(float(p.montant_fcfa or 0) for p in liste)
        intervalles = [(float(p.volume_litres), _km(p)) for p in liste if _km(p)]
        km = sum(k for _, k in intervalles)
        conso = sum(l for l, _ in intervalles) / km * 100 if km else None
        ref = float(v.conso_theorique_origine or 0) or None
        hors = sum(float(p.volume_litres) for p in liste if p.type_mouvement != 'tournee')
        derniere = liste[-1]
        lignes.append({
            'vehicule_id': str(v.id), 'immatriculation': v.immatriculation,
            'marque': v.marque_str, 'modele': v.modele_str,
            'type_vehicule': v.get_type_vehicule_display(), 'agence_nom': v.agence.nom if v.agence else None,
            'nb_prises': len(liste), 'nb_intervalles': len(intervalles),
            'km_parcourus': km or None, 'litres': _r(litres), 'montant': _r(montant),
            'conso_moyenne': _r(conso), 'conso_reference': _r(ref),
            'ecart_100': _r(conso - ref) if conso is not None and ref else None,
            'ecart_pct': _r((conso / ref - 1) * 100, 1) if conso is not None and ref else None,
            'derniere_conso': _r(float(derniere.consommation_calculee))
                              if derniere.consommation_calculee is not None else None,
            'derniere_date': derniere.date_plein,
            'nb_anomalies': sum(1 for p in liste if p.statut_validation == 'anomalie'),
            'part_hors_tournee': _r(hors / litres * 100, 1) if litres else None,
            'premiere_date': liste[0].date_plein,
            'historique_insuffisant': not intervalles,
        })
    lignes.sort(key=lambda l: (l['ecart_pct'] is None, -(l['ecart_pct'] or 0), l['immatriculation']))
    return lignes


# ── Évolution mensuelle par agence ────────────────────────────────────

def evolution_agences(prises, tournees_effectuees, debut, fin):
    """Séries mensuelles (mois vides à 0) par agence : litres, montant, nombre
    de prises, km, conso, découpés tournées / hors tournée, et dotation
    théorique des tournées commencées dans le mois."""
    mois = mois_entre(debut, fin)
    vide = lambda: {'volume': 0.0, 'volume_tournee': 0.0, 'volume_hors': 0.0, 'montant': 0.0,
                    'montant_tournee': 0.0, 'montant_hors': 0.0, 'nb': 0, 'nb_tournee': 0, 'nb_hors': 0,
                    'km': 0, 'litres_km': 0.0, 'dotation_theorique': 0.0}
    agences = {}

    def point(nom, m):
        a = agences.setdefault(nom, {'nom': nom, 'points': {x: vide() for x in mois}})
        return a['points'].get(m)

    for p in prises:
        pt = point(p.agence.nom if p.agence else 'Sans agence', p.date_plein.strftime('%Y-%m'))
        if pt is None:
            continue
        vol, mt = float(p.volume_litres), float(p.montant_fcfa or 0)
        cote = 'tournee' if p.type_mouvement == 'tournee' else 'hors'
        pt['volume'] += vol; pt[f'volume_{cote}'] += vol
        pt['montant'] += mt; pt[f'montant_{cote}'] += mt
        pt['nb'] += 1; pt[f'nb_{cote}'] += 1
        km = _km(p)
        if km:
            pt['km'] += km; pt['litres_km'] += vol
    for te in tournees_effectuees:
        pt = point(te.agence.nom, te.date_debut.strftime('%Y-%m'))
        if pt is not None:
            pt['dotation_theorique'] += te.dotation_theorique or 0

    resultat = []
    for a in sorted(agences.values(), key=lambda x: x['nom']):
        points = []
        for m in mois:
            pt = a['points'][m]
            litres_km = pt.pop('litres_km')
            pt['conso'] = _r(litres_km / pt['km'] * 100) if pt['km'] else None
            points.append({'mois': m, **{k: _r(v) if isinstance(v, float) else v for k, v in pt.items()}})
        resultat.append({'nom': a['nom'], 'points': points})
    return {'mois': mois, 'agences': resultat}


# ── Rapprochement TotalEnergies ───────────────────────────────────────

def transactions_effectives(transactions):
    """Ventes non annulées : une annulation (volume négatif) porte le code
    d'autorisation de la vente annulée, précédé d'un « - »."""
    annules = {t.code_autorisation.lstrip('-') for t in transactions
               if (t.volume or 0) < 0 and t.code_autorisation}
    return [t for t in transactions
            if (t.volume or 0) > 0 and not (t.code_autorisation and t.code_autorisation in annules)]


def _quand_prise(p):
    return datetime.combine(p.date_plein, p.heure_plein or dtime(12, 0))


def _quand_transaction(t):
    return datetime.combine(t.date_transaction, t.heure_transaction or dtime(12, 0))


def _conso_total(transactions):
    """Conso L/100 côté Total, même méthode que UbiFleet : litres hors 1re
    transaction ÷ (km de la dernière − km de la 1re), en ignorant les
    kilométrages nuls ou qui reculent."""
    suite, dernier_km = [], None
    for t in sorted(transactions, key=_quand_transaction):
        km = float(t.kilometrage_actuel or 0)
        if km <= 0 or (dernier_km is not None and km < dernier_km):
            continue
        suite.append((float(t.volume), km))
        dernier_km = km
    if len(suite) < 2 or suite[-1][1] <= suite[0][1]:
        return None, None
    km = suite[-1][1] - suite[0][1]
    return _r(sum(v for v, _ in suite[1:]) / km * 100), int(km)


def rapprocher(prises, transactions, vehicules, tolerance_heures, ecart_pct, periode=None):
    """Synthèse par véhicule, lignes appariées / isolées, plaques Total inconnues.
    `periode` (début, fin) : les transactions hors période (marge chargée pour
    les prises proches de minuit) ne comptent que si elles sont rapprochées."""
    dans_periode = (lambda d: periode[0] <= d <= periode[1]) if periode else (lambda d: True)
    par_carte = {normaliser_carte(v.numero_carte_carburant): v for v in vehicules if v.numero_carte_carburant}
    par_plaque = {normaliser_immat(v.immatriculation): v for v in vehicules}

    tx_par_vehicule, inconnues = defaultdict(list), defaultdict(lambda: {'nb': 0, 'volume': 0.0, 'montant': 0.0})
    for t in transactions_effectives(transactions):
        v = par_carte.get(normaliser_carte(t.numero_moyen_paiement)) or par_plaque.get(normaliser_immat(t.immatriculation))
        if v is None:
            if not dans_periode(t.date_transaction):
                continue
            i = inconnues[t.immatriculation or '(vide)']
            i['nb'] += 1; i['volume'] += float(t.volume); i['montant'] += float(t.montant or 0)
            continue
        tx_par_vehicule[v.pk].append(t)
    prises_par_vehicule = defaultdict(list)
    for p in prises:
        prises_par_vehicule[p.vehicule_id].append(p)

    tolerance = timedelta(hours=tolerance_heures)
    lignes, synthese = [], []
    vehicules_par_id = {v.pk: v for v in vehicules}
    for vid in set(tx_par_vehicule) | set(prises_par_vehicule):
        v = vehicules_par_id.get(vid) or prises_par_vehicule[vid][0].vehicule
        ps, ts = prises_par_vehicule.get(vid, []), tx_par_vehicule.get(vid, [])
        # Paires candidates, de la plus proche (heure, puis volume) à la moins proche
        candidats = []
        for i, p in enumerate(ps):
            for j, t in enumerate(ts):
                dt = abs(_quand_prise(p) - _quand_transaction(t))
                if dt <= tolerance:
                    vp, vt = float(p.volume_litres), float(t.volume)
                    score = dt / tolerance + abs(vp - vt) / max(vp, vt, 1)
                    candidats.append((score, i, j))
        candidats.sort()
        pris_p, pris_t, paires = set(), set(), []
        for _, i, j in candidats:
            if i not in pris_p and j not in pris_t:
                pris_p.add(i); pris_t.add(j); paires.append((ps[i], ts[j]))

        stats = defaultdict(int)
        for p, t in paires:
            vp, vt = float(p.volume_litres), float(t.volume)
            mp, mt = float(p.montant_fcfa or 0), float(t.montant or 0)
            e_vol = (vp - vt) / vt * 100 if vt else None
            e_mt = (mp - mt) / mt * 100 if mt else None
            statut = 'ecart' if (e_vol is not None and abs(e_vol) > ecart_pct) \
                or (e_mt is not None and abs(e_mt) > ecart_pct) else 'rapproche'
            stats[statut] += 1
            lignes.append(_ligne(v, statut, p, t, e_vol, e_mt))
        for i, p in enumerate(ps):
            if i not in pris_p:
                stats['prise_sans_transaction'] += 1
                lignes.append(_ligne(v, 'prise_sans_transaction', p, None))
        for j, t in enumerate(ts):
            if j not in pris_t and dans_periode(t.date_transaction):
                stats['transaction_sans_prise'] += 1
                lignes.append(_ligne(v, 'transaction_sans_prise', None, t))
        ts = [t for j, t in enumerate(ts) if j in pris_t or dans_periode(t.date_transaction)]
        if not ps and not ts:
            continue

        l_ubi = sum(float(p.volume_litres) for p in ps)
        l_tot = sum(float(t.volume) for t in ts)
        m_ubi = sum(float(p.montant_fcfa or 0) for p in ps)
        m_tot = sum(float(t.montant or 0) for t in ts)
        intervalles = [(float(p.volume_litres), _km(p)) for p in ps if _km(p)]
        km_ubi = sum(k for _, k in intervalles)
        conso_tot, km_tot = _conso_total(ts)
        synthese.append({
            'vehicule_id': str(v.pk), 'immatriculation': v.immatriculation,
            'carte': bool(v.numero_carte_carburant),
            'nb_prises': len(ps), 'nb_transactions': len(ts),
            'litres_declares': _r(l_ubi), 'litres_factures': _r(l_tot), 'ecart_litres': _r(l_ubi - l_tot),
            'montant_declare': _r(m_ubi), 'montant_facture': _r(m_tot), 'ecart_montant': _r(m_ubi - m_tot),
            'nb_rapproches': stats['rapproche'], 'nb_ecarts': stats['ecart'],
            'nb_transactions_sans_prise': stats['transaction_sans_prise'],
            'nb_prises_sans_transaction': stats['prise_sans_transaction'],
            'conso_ubifleet': _r(sum(l for l, _ in intervalles) / km_ubi * 100) if km_ubi else None,
            'conso_total': conso_tot, 'km_total': km_tot,
        })
    synthese.sort(key=lambda s: (-abs(s['ecart_litres'] or 0), s['immatriculation']))
    lignes.sort(key=lambda l: (l['immatriculation'], l['quand'] or ''))
    totaux = {k: _r(sum(s[k] or 0 for s in synthese)) for k in (
        'litres_declares', 'litres_factures', 'ecart_litres', 'montant_declare', 'montant_facture', 'ecart_montant',
        'nb_rapproches', 'nb_ecarts', 'nb_transactions_sans_prise', 'nb_prises_sans_transaction')}
    return {
        'synthese': synthese, 'lignes': lignes, 'totaux': totaux,
        'immatriculations_inconnues': sorted(
            [{'immatriculation': k, 'nb': i['nb'], 'volume': _r(i['volume']), 'montant': _r(i['montant'])}
             for k, i in inconnues.items()], key=lambda x: -x['volume']),
        'parametres': {'tolerance_heures': tolerance_heures, 'ecart_pct': ecart_pct},
    }


def _ligne(v, statut, p, t, e_vol=None, e_mt=None):
    quand = _quand_prise(p) if p else _quand_transaction(t)
    return {
        'statut': statut, 'vehicule_id': str(v.pk), 'immatriculation': v.immatriculation,
        'quand': quand.isoformat(),
        'prise_id': str(p.id) if p else None,
        'prise_date': p.date_plein if p else None, 'prise_heure': p.heure_plein if p else None,
        'prise_volume': _r(float(p.volume_litres)) if p else None,
        'prise_montant': _r(float(p.montant_fcfa or 0)) if p else None,
        'prise_station': p.station.nom if p and p.station else None,
        'prise_chauffeur': p.chauffeur.nom_complet if p and p.chauffeur else None,
        'transaction_id': t.pk if t else None,
        'transaction_date': t.date_transaction if t else None,
        'transaction_heure': t.heure_transaction if t else None,
        'transaction_volume': _r(float(t.volume)) if t else None,
        'transaction_montant': _r(float(t.montant or 0)) if t else None,
        'transaction_station': t.nom_station if t else None,
        'transaction_chauffeur': t.nom_chauffeur if t else None,
        'transaction_ticket': t.numero_ticket if t else None,
        'ecart_volume_pct': _r(e_vol, 1), 'ecart_montant_pct': _r(e_mt, 1),
        # Chauffeur de la prise ≠ chauffeur de la carte Total (n° chauffeur Total de sa fiche)
        'chauffeur_different': bool(p and t and p.chauffeur and p.chauffeur.numero_chauffeur_total
                                    and t.numero_chauffeur
                                    and p.chauffeur.numero_chauffeur_total.lstrip('0') != t.numero_chauffeur.lstrip('0')),
    }

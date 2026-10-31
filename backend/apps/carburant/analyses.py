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
        montant_intervalles = sum(float(p.montant_fcfa or 0) for p in liste if _km(p))
        ref = float(v.conso_theorique_origine or 0) or None
        hors = sum(float(p.volume_litres) for p in liste if p.type_mouvement != 'tournee')
        derniere = liste[-1]
        lignes.append({
            'vehicule_id': str(v.id), 'immatriculation': v.immatriculation,
            'marque': v.marque_str, 'modele': v.modele_str,
            'type_vehicule': v.get_type_vehicule_display(), 'agence_nom': v.agence.nom if v.agence else None,
            'nb_prises': len(liste), 'nb_intervalles': len(intervalles),
            'km_parcourus': km or None, 'litres': _r(litres), 'montant': _r(montant),
            'cout_km': _r(montant_intervalles / km) if km else None,
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


def classement_chauffeurs(prises):
    """Une ligne par chauffeur : intervalles (plein à plein) de ses prises,
    consommation comparée à la référence pondérée des véhicules conduits."""
    groupes = defaultdict(list)
    for p in prises:
        groupes[p.chauffeur_id].append(p)
    lignes = []
    for cid, liste in groupes.items():
        c = liste[0].chauffeur
        litres_int = km = ref_km = km_ref = 0.0
        for p in liste:
            k = _km(p)
            if not k:
                continue
            litres_int += float(p.volume_litres)
            km += k
            ref = float(p.vehicule.conso_theorique_origine or 0)
            if ref:
                ref_km += ref * k
                km_ref += k
        conso = litres_int / km * 100 if km else None
        ref = ref_km / km_ref if km_ref else None
        lignes.append({
            'chauffeur_id': str(cid) if cid else None,
            'chauffeur': (f"{c.matricule} — {c.nom_complet}" if c.matricule else c.nom_complet) if c else 'Sans chauffeur',
            'nb_prises': len(liste), 'nb_vehicules': len({p.vehicule_id for p in liste}),
            'litres': _r(sum(float(p.volume_litres) for p in liste)),
            'montant': _r(sum(float(p.montant_fcfa or 0) for p in liste)),
            'km_parcourus': int(km) or None, 'conso_moyenne': _r(conso), 'conso_reference': _r(ref),
            'ecart_pct': _r((conso / ref - 1) * 100, 1) if conso is not None and ref else None,
            'nb_anomalies': sum(1 for p in liste if p.statut_validation == 'anomalie'),
        })
    lignes.sort(key=lambda l: (l['chauffeur_id'] is None, l['ecart_pct'] is None, -(l['ecart_pct'] or 0)))
    return lignes


def conso_ponderee(lignes):
    """Conso globale de lignes de consommation_vehicules : litres des
    intervalles ÷ km × 100 (pondérée par les km, pas une moyenne de moyennes)."""
    km = sum(l['km_parcourus'] or 0 for l in lignes if l['conso_moyenne'] is not None)
    litres = sum(l['conso_moyenne'] * l['km_parcourus'] / 100 for l in lignes if l['conso_moyenne'] is not None)
    return _r(litres / km * 100) if km else None


def classement_ecarts(lignes, n=10):
    """Véhicules qui consomment le plus au-dessus de leur référence."""
    avec = [l for l in lignes if l['ecart_pct'] is not None]
    return sorted(avec, key=lambda l: -l['ecart_pct'])[:n]


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


def associer_transactions(transactions, vehicules, dans_periode=lambda d: True):
    """Transactions effectives par véhicule (carte carburant, sinon plaque
    normalisée, y compris ses anciennes plaques) et plaques inconnues."""
    from apps.vehicules.models import HistoriqueImmatriculation
    par_carte = {normaliser_carte(v.numero_carte_carburant): v for v in vehicules if v.numero_carte_carburant}
    par_plaque = {normaliser_immat(v.immatriculation): v for v in vehicules}
    ids = {v.pk: v for v in vehicules}
    for h in HistoriqueImmatriculation.objects.filter(vehicule_id__in=ids):
        par_plaque.setdefault(normaliser_immat(h.ancienne_immatriculation), ids[h.vehicule_id])
    tx_par_vehicule, inconnues = defaultdict(list), defaultdict(lambda: {'nb': 0, 'volume': 0.0, 'montant': 0.0})
    for t in transactions_effectives(transactions):
        v = par_carte.get(normaliser_carte(t.numero_moyen_paiement)) or par_plaque.get(normaliser_immat(t.immatriculation))
        if v is None:
            if dans_periode(t.date_transaction):
                i = inconnues[t.immatriculation or '(vide)']
                i['nb'] += 1; i['volume'] += float(t.volume); i['montant'] += float(t.montant or 0)
            continue
        tx_par_vehicule[v.pk].append(t)
    return tx_par_vehicule, inconnues


def rapprocher(prises, transactions, vehicules, tolerance_heures, ecart_pct, periode=None):
    """Synthèse par véhicule, lignes appariées / isolées, plaques Total inconnues.
    `periode` (début, fin) : les transactions hors période (marge chargée pour
    les prises proches de minuit) ne comptent que si elles sont rapprochées."""
    dans_periode = (lambda d: periode[0] <= d <= periode[1]) if periode else (lambda d: True)
    tx_par_vehicule, inconnues = associer_transactions(transactions, vehicules, dans_periode)
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


# ── Consommation facturée (litres Total ÷ km du compteur UbiFleet) ────

def compteur_a(saisies, quand):
    """Kilométrage estimé à un instant : interpolation linéaire entre la
    dernière saisie (relevé ou prise) d'avant et la première d'après."""
    avant = apres = None
    for q, km in saisies:
        if q <= quand:
            avant = (q, km)
        elif apres is None:
            apres = (q, km)
            break
    if avant and apres:
        duree = (apres[0] - avant[0]).total_seconds()
        if duree <= 0:
            return float(avant[1])
        return avant[1] + (apres[1] - avant[1]) * (quand - avant[0]).total_seconds() / duree
    if avant:
        return float(avant[1])
    return float(apres[1]) if apres else None


def consommation_facturee(vehicules, saisies_par_vehicule, prises_periode, transactions, periode):
    """Par véhicule : litres facturés par Total (ventes non annulées) entre la
    1re et la dernière transaction de la période, hors 1re (plein à plein),
    rapportés aux km du compteur UbiFleet entre ces deux transactions.
    Comparée à la consommation déclarée (prises) et à la référence."""
    debut, fin = periode
    tx_par_vehicule, inconnues = associer_transactions(transactions, vehicules, lambda d: debut <= d <= fin)
    declarees = {l['vehicule_id']: l for l in consommation_vehicules(prises_periode)}
    lignes = []
    for v in vehicules:
        ts = sorted((t for t in tx_par_vehicule.get(v.pk, []) if debut <= t.date_transaction <= fin),
                    key=_quand_transaction)
        d = declarees.get(str(v.pk))
        if not ts and not d:
            continue
        saisies = saisies_par_vehicule.get(v.pk, [])
        litres_factures = sum(float(t.volume) for t in ts)
        km = km_debut = km_fin = conso = None
        if len(ts) >= 2:
            km_debut = compteur_a(saisies, _quand_transaction(ts[0]))
            km_fin = compteur_a(saisies, _quand_transaction(ts[-1]))
            if km_debut is not None and km_fin is not None and km_fin > km_debut:
                km = km_fin - km_debut
                conso = sum(float(t.volume) for t in ts[1:]) / km * 100
        ref = float(v.conso_theorique_origine or 0) or None
        conso_declaree = d['conso_moyenne'] if d else None
        lignes.append({
            'vehicule_id': str(v.pk), 'immatriculation': v.immatriculation,
            'marque': v.marque_str, 'modele': v.modele_str, 'type_vehicule': v.get_type_vehicule_display(),
            'agence_nom': v.agence.nom if v.agence else None, 'carte': bool(v.numero_carte_carburant),
            'nb_transactions': len(ts), 'litres_factures': _r(litres_factures),
            'montant_facture': _r(sum(float(t.montant or 0) for t in ts)),
            'premiere_transaction': _quand_transaction(ts[0]).isoformat() if ts else None,
            'derniere_transaction': _quand_transaction(ts[-1]).isoformat() if ts else None,
            'km_debut': _r(km_debut, 0), 'km_fin': _r(km_fin, 0), 'km_parcourus': _r(km, 0),
            'conso_facturee': _r(conso),
            'nb_prises': d['nb_prises'] if d else 0, 'litres_declares': d['litres'] if d else 0,
            'conso_declaree': conso_declaree, 'conso_reference': _r(ref),
            'ecart_reference_pct': _r((conso / ref - 1) * 100, 1) if conso is not None and ref else None,
            'ecart_declaree_pct': _r((conso / conso_declaree - 1) * 100, 1)
                                  if conso is not None and conso_declaree else None,
            'motif': None if conso is not None else (
                'aucune transaction Total' if not ts else
                'une seule transaction Total' if len(ts) < 2 else
                'compteur UbiFleet insuffisant (relevés ou prises) entre les transactions'),
        })
    lignes.sort(key=lambda l: (l['ecart_reference_pct'] is None, -(l['ecart_reference_pct'] or 0), l['immatriculation']))
    return {
        'resultats': lignes,
        'immatriculations_inconnues': sorted(
            [{'immatriculation': k, 'nb': i['nb'], 'volume': _r(i['volume']), 'montant': _r(i['montant'])}
             for k, i in inconnues.items()], key=lambda x: -x['volume']),
    }

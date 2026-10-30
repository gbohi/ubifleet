"""UbiFleet — Suivi des tournées et des prises hors tournée.

Tournée effectuée (une ligne) : litres et montants = somme de ses prises ;
KM départ = 1re prise, KM retour = saisi à la clôture (dernière prise tant
qu'elle est en cours) ; théorique figé à l'ouverture ; montant théorique =
dotation théorique × prix du litre en vigueur au début de la tournée.

Prise hors tournée (une ligne) : km parcourus depuis la prise précédente ;
litres estimés = km × consommation théorique de référence du véhicule
(à défaut, moyenne observée sur ses prises) ÷ 100.
"""

from .models import PrixCarburant
from .anomalies import ordre_chronologique


def _r(x, n=2):
    return round(x, n) if x is not None else None


def ligne_tournee(te, prix_cache):
    prises = sorted(te.prises.all(), key=ordre_chronologique)
    litres = sum(float(p.volume_litres) for p in prises)
    montant = sum(float(p.montant_fcfa or 0) for p in prises)
    v = te.vehicule
    cloturee = te.statut == te.Statut.CLOTUREE
    km_retour = te.km_retour if cloturee else (prises[-1].kilometrage_releve if prises else te.km_depart)
    km = km_retour - te.km_depart if km_retour is not None else None
    km = km if km and km > 0 else None

    cle = (v.type_carburant, te.date_debut)
    if cle not in prix_cache:
        prix = PrixCarburant.en_vigueur(v.type_carburant, te.date_debut)
        prix_cache[cle] = float(prix.prix) if prix else None
    prix = prix_cache[cle]
    dot = te.dotation_theorique or None
    km_theo = te.km_theorique or None
    conso = litres / km * 100 if km else None
    conso_theo = dot / km_theo * 100 if dot and km_theo else None
    return {
        'id': str(te.id), 'numero': te.numero, 'statut': te.statut, 'statut_display': te.get_statut_display(),
        'a_verifier': te.a_verifier,
        'date_debut': te.date_debut, 'heure_debut': te.heure_debut,
        'date_fin': te.date_fin, 'heure_fin': te.heure_fin,
        'vehicule_id': str(v.id), 'immatriculation': v.immatriculation,
        'type_vehicule': v.get_type_vehicule_display(),
        'tournee_id': te.tournee_id, 'tournee_code': te.tournee.code, 'tournee_libelle': te.tournee.libelle,
        'chauffeur_nom': te.chauffeur.nom_complet if te.chauffeur else None,
        'agence_nom': te.agence.nom,
        'nb_prises': len(prises),
        'vol_reel': _r(litres), 'montant_reel': _r(montant),
        'km_depart': te.km_depart, 'km_retour': km_retour, 'km_parcouru': km,
        'km_theorique': km_theo, 'vol_theorique': dot,
        'montant_theorique': _r(dot * prix) if dot and prix else None,
        'conso_reel': _r(conso), 'conso_theorique': _r(conso_theo),
        'ecart_dotation': _r(litres - dot) if dot else None,
        'ecart_conso': _r(conso - conso_theo, 1) if conso is not None and conso_theo is not None else None,
        'commentaire': te.commentaire, 'motif_annulation': te.motif_annulation,
        'prises': [{
            'id': str(p.id), 'date': p.date_plein, 'heure': p.heure_plein,
            'volume': float(p.volume_litres), 'montant': float(p.montant_fcfa or 0),
            'kilometrage': p.kilometrage_releve, 'station': p.station.nom if p.station else None,
        } for p in prises],
    }


def ligne_hors_tournee(p, types, ref_cache):
    v = p.vehicule
    if v.pk not in ref_cache:
        ref, source = float(v.conso_theorique_origine or 0), 'reference'
        if not ref:
            ref, source = v.consommation_moyenne(), 'moyenne'
        ref_cache[v.pk] = (ref or None, source if ref else None)
    ref, source = ref_cache[v.pk]
    km = None
    if p.kilometrage_depart is not None and p.kilometrage_releve > p.kilometrage_depart:
        km = p.kilometrage_releve - p.kilometrage_depart
    litres = float(p.volume_litres)
    estimes = km * ref / 100 if km and ref else None
    t = types.get(p.type_mouvement)
    return {
        'id': str(p.id), 'date': p.date_plein, 'heure': p.heure_plein,
        'vehicule_id': str(v.id), 'immatriculation': v.immatriculation,
        'type_vehicule': v.get_type_vehicule_display(),
        'type_mouvement': p.type_mouvement, 'type_display': t.libelle if t else p.type_mouvement,
        'type_couleur': t.couleur if t else 'gray',
        'chauffeur_nom': p.chauffeur.nom_complet if p.chauffeur else None,
        'agence_nom': p.agence.nom, 'notes': p.notes,
        'km_depart': p.kilometrage_depart, 'km_retour': p.kilometrage_releve, 'km_parcouru': km,
        'vol_reel': _r(litres), 'montant_reel': _r(float(p.montant_fcfa or 0)),
        'conso_reel': _r(float(p.consommation_calculee)) if p.consommation_calculee is not None else None,
        'conso_reference': _r(ref), 'source_reference': source,
        'vol_estime': _r(estimes), 'ecart': _r(litres - estimes) if estimes is not None else None,
    }


def synthese(lignes_tournees, lignes_hors):
    lt = [l for l in lignes_tournees if l['statut'] != 'annulee']
    vol_t = sum(l['vol_reel'] or 0 for l in lt)
    vol_h = sum(l['vol_reel'] or 0 for l in lignes_hors)
    mt_t = sum(l['montant_reel'] or 0 for l in lt)
    mt_h = sum(l['montant_reel'] or 0 for l in lignes_hors)
    total = vol_t + vol_h
    return {
        'nb_tournees': len(lt), 'nb_en_cours': sum(1 for l in lt if l['statut'] == 'en_cours'),
        'vol_tournees': _r(vol_t), 'montant_tournees': _r(mt_t),
        'vol_theorique_tournees': _r(sum(l['vol_theorique'] or 0 for l in lt)),
        'nb_prises_hors': len(lignes_hors), 'vol_hors': _r(vol_h), 'montant_hors': _r(mt_h),
        'vol_estime_hors': _r(sum(l['vol_estime'] or 0 for l in lignes_hors)),
        'part_hors_pct': _r(vol_h / total * 100, 1) if total else None,
    }

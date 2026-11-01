"""UbiFleet — Récapitulatifs des dépenses (état des dépenses, rapport des coûts)."""

from django.db.models import Count, Sum


def recapitulatif(qs):
    """Totaux d'un ensemble de dépenses : par catégorie, par poste du budget et
    par origine (nombre, montant, part du total en %)."""
    from apps.parametrage.models import CategorieDepense
    from .automatiques import ORIGINES
    qs = qs.order_by()
    total = float(qs.aggregate(t=Sum('montant'))['t'] or 0)
    cats = {c.code: c for c in CategorieDepense.objects.all()}
    postes = dict(CategorieDepense.PosteBudget.choices)

    def part(montant):
        return round(montant * 100 / total, 1) if total else 0

    par_categorie, par_poste = [], {}
    for r in qs.values('categorie').annotate(nb=Count('id'), t=Sum('montant')).order_by('-t'):
        c = cats.get(r['categorie'])
        poste = c.poste_budget if c else 'divers'
        montant = float(r['t'] or 0)
        par_categorie.append({'categorie': r['categorie'], 'libelle': c.libelle if c else r['categorie'],
                              'poste': poste, 'poste_libelle': postes.get(poste, poste),
                              'nb': r['nb'], 'total': montant, 'part': part(montant)})
        p = par_poste.setdefault(poste, {'poste': poste, 'libelle': postes.get(poste, poste), 'nb': 0, 'total': 0.0})
        p['nb'] += r['nb']
        p['total'] += montant
    for p in par_poste.values():
        p['part'] = part(p['total'])
    par_origine = [{'origine': r['ref_objet_type'] or 'manuelle',
                    'libelle': ORIGINES.get(r['ref_objet_type'], 'Saisie manuelle'),
                    'nb': r['nb'], 'total': float(r['t'] or 0), 'part': part(float(r['t'] or 0))}
                   for r in qs.values('ref_objet_type').annotate(nb=Count('id'), t=Sum('montant')).order_by('-t')]
    return {
        'total': total, 'nb': qs.count(),
        'par_categorie': par_categorie,
        'par_poste': sorted(par_poste.values(), key=lambda p: -p['total']),
        'par_origine': par_origine,
    }


def postes_des_categories():
    """{code catégorie: poste du budget}."""
    from apps.parametrage.models import CategorieDepense
    return dict(CategorieDepense.objects.values_list('code', 'poste_budget'))

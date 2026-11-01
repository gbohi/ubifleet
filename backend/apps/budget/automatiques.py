"""UbiFleet — Dépenses reportées automatiquement depuis les autres modules.

Chaque coût déjà saisi ailleurs a sa ligne de dépense (DepenseVehicule),
créée, mise à jour et supprimée avec sa source ; elle ne se modifie que par
la source (cf. DepenseViewSet). Le budget, le coût au km et les rapports
comptent ainsi tous les coûts sans ressaisie.

  prise de carburant   → « Carburant »             montant de la prise
  intervention terminée → selon le type d'intervention, coût réel
  pneu                 → « Pneumatiques »          coût du pneu, au montage
  contrat d'assurance  → « Assurance »             prime, au début du contrat
  sinistre             → « Sinistre »              coût de réparation − indemnisation reçue

Les fonctions `champs_*` ne lisent que des champs : elles servent aussi à la
reprise des données existantes (migration).
"""

from decimal import Decimal

REF_PRISE        = 'prise_carburant'
REF_INTERVENTION = 'intervention'
REF_PNEU         = 'pneu'
REF_CONTRAT      = 'contrat_assurance'
REF_SINISTRE     = 'sinistre'

#: Origine affichée dans l'état des dépenses ; '' = saisie manuelle
ORIGINES = {
    REF_PRISE: 'Prise de carburant', REF_INTERVENTION: 'Intervention', REF_PNEU: 'Pneu',
    REF_CONTRAT: "Contrat d'assurance", REF_SINISTRE: 'Sinistre',
}
#: Où modifier une dépense automatique
MODIFIER_DANS = {
    REF_PRISE: 'la prise de carburant (Carburant)', REF_INTERVENTION: "l'intervention (Entretiens)",
    REF_PNEU: 'le suivi des pneus (Entretiens)', REF_CONTRAT: "le contrat d'assurance (Sinistres & Assurances)",
    REF_SINISTRE: 'le sinistre (Sinistres & Assurances)',
}

#: Catégorie de dépense selon la catégorie du type d'intervention
CATEGORIE_INTERVENTION = {
    'preventif': 'entretien', 'curatif': 'reparation', 'pneus': 'pneus',
    'carrosserie': 'reparation', 'controle': 'controle', 'autre': 'divers',
}
#: Catégories alimentées automatiquement : ni suppression ni désactivation
CATEGORIES_SYSTEME = ['carburant', 'entretien', 'reparation', 'pneus', 'assurance', 'sinistre', 'controle', 'divers']


def _date(valeur):
    """Date d'un champ (chaîne ISO si l'objet vient d'être créé par le code)."""
    import datetime
    return datetime.date.fromisoformat(valeur) if isinstance(valeur, str) else valeur


def _positif(montant):
    return montant is not None and Decimal(montant) > 0


def champs_prise(prise):
    if not _positif(prise.montant_fcfa):
        return None
    tournee = prise.tournee.code if prise.tournee_id else ''
    return {
        'vehicule_id': prise.vehicule_id, 'agence_id': prise.agence_id, 'categorie': 'carburant',
        'date_depense': prise.date_plein, 'montant': prise.montant_fcfa,
        'description': f"Prise de carburant — {prise.volume_litres} L" + (f" ({tournee})" if tournee else ''),
        'fournisseur': prise.station.nom if prise.station_id else '',
        'numero_facture': prise.bon_carburant or '',
    }


def champs_intervention(i):
    if i.statut != 'termine' or not _positif(i.cout_reel):
        return None
    type_i = i.type_intervention
    return {
        'vehicule_id': i.vehicule_id, 'agence_id': i.agence_id,
        'categorie': CATEGORIE_INTERVENTION.get(type_i.categorie, 'divers'),
        'date_depense': i.date_fin or i.date_debut or i.date_planifiee, 'montant': i.cout_reel,
        'description': f"Intervention — {type_i.nom}",
        'fournisseur': i.prestataire.nom if i.prestataire_id else '', 'numero_facture': '',
    }


def champs_pneu(p):
    if not _positif(p.cout):
        return None
    return {
        'vehicule_id': p.vehicule_id, 'agence_id': p.vehicule.agence_id, 'categorie': 'pneus',
        'date_depense': p.date_montage, 'montant': p.cout,
        'description': f"Pneu {p.position.replace('_', ' ')}" + (f" — {p.marque}" if p.marque else '')
                       + (f" {p.dimension}" if p.dimension else ''),
        'fournisseur': '', 'numero_facture': '',
    }


def champs_contrat(c):
    if not _positif(c.prime_annuelle):
        return None
    return {
        'vehicule_id': c.vehicule_id, 'agence_id': c.vehicule.agence_id, 'categorie': 'assurance',
        'date_depense': c.date_debut, 'montant': c.prime_annuelle,
        'description': f"Prime d'assurance — police {c.numero_police} ({_date(c.date_debut):%d/%m/%Y} → {_date(c.date_fin):%d/%m/%Y})",
        'fournisseur': c.assureur.nom if c.assureur_id else '', 'numero_facture': c.numero_police,
    }


def champs_sinistre(s):
    """À la charge de l'entreprise : coût de réparation − indemnisation reçue
    (coût total tant que l'indemnisation n'est pas saisie)."""
    if not _positif(s.cout_reparation):
        return None
    cout, indemnite = Decimal(s.cout_reparation), Decimal(s.indemnisation_recue or 0)
    reste = cout - indemnite
    if reste <= 0:
        return None
    detail = f" − indemnisation {indemnite:,.0f}".replace(',', ' ') if indemnite else ''
    return {
        'vehicule_id': s.vehicule_id, 'agence_id': s.agence_id, 'categorie': 'sinistre',
        'date_depense': s.date_sinistre, 'montant': reste,
        'description': f"Sinistre {s.numero_dossier} — réparation {cout:,.0f}".replace(',', ' ') + detail,
        'fournisseur': '', 'numero_facture': s.numero_dossier,
    }


def synchroniser(DepenseVehicule, ref_type, source, champs):
    """Crée, met à jour ou supprime la dépense de `source` (champs None → supprimée)."""
    qs = DepenseVehicule.objects.filter(ref_objet_type=ref_type, ref_objet_id=source.pk)
    if champs is None:
        qs.delete()
        return
    if not qs.update(**champs):
        DepenseVehicule.objects.create(ref_objet_type=ref_type, ref_objet_id=source.pk,
                                       created_by_id=getattr(source, 'created_by_id', None), **champs)


def supprimer(ref_type, source_pk):
    from .models import DepenseVehicule
    DepenseVehicule.objects.filter(ref_objet_type=ref_type, ref_objet_id=source_pk).delete()


def connecter_signaux():
    """Branche le report automatique sur les modèles sources (BudgetConfig.ready)."""
    from django.db.models.signals import post_delete, post_save
    from apps.entretien.models import Intervention, SuiviPneus
    from apps.sinistres.models import ContratAssurance, Sinistre
    from .models import DepenseVehicule

    for modele, ref, champs in ((Intervention, REF_INTERVENTION, champs_intervention),
                                (SuiviPneus, REF_PNEU, champs_pneu),
                                (ContratAssurance, REF_CONTRAT, champs_contrat),
                                (Sinistre, REF_SINISTRE, champs_sinistre)):
        def enregistre(sender, instance, raw=False, _ref=ref, _champs=champs, **kwargs):
            if not raw:
                synchroniser(DepenseVehicule, _ref, instance, _champs(instance))

        def supprime(sender, instance, _ref=ref, **kwargs):
            supprimer(_ref, instance.pk)

        post_save.connect(enregistre, sender=modele, weak=False, dispatch_uid=f'depense_auto_save_{ref}')
        post_delete.connect(supprime, sender=modele, weak=False, dispatch_uid=f'depense_auto_delete_{ref}')

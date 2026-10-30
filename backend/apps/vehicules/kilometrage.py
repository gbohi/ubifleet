"""UbiFleet — Cohérence du kilométrage d'un véhicule.

Le compteur d'un véhicule est déduit de ses saisies : c'est le plus grand
kilométrage parmi ses relevés et ses pleins, sans descendre sous son
kilométrage d'entrée dans le parc. Il est recalculé après chaque saisie,
correction ou suppression, de sorte qu'une erreur corrigée ne laisse pas
le compteur faussé.

Un kilométrage saisi est contrôlé par rapport aux saisies voisines (jours
précédents et suivants), et non par rapport au compteur actuel : on peut
ainsi corriger une valeur trop élevée ou saisir un relevé antérieur.
"""

from django.db.models import Max
from rest_framework import serializers


def _sources(vehicule, exclure=None):
    """(queryset, champ km, champ date, libellé) des saisies kilométriques du véhicule.
    `exclure` : instance à ignorer (la saisie en cours de correction)."""
    from apps.carburant.models import PleinsCarburant
    from apps.vehicules.models import ReleveKilometrage
    pleins = PleinsCarburant.objects.filter(vehicule=vehicule)
    releves = ReleveKilometrage.objects.filter(vehicule=vehicule)
    if isinstance(exclure, PleinsCarburant) and exclure.pk:
        pleins = pleins.exclude(pk=exclure.pk)
    if isinstance(exclure, ReleveKilometrage) and exclure.pk:
        releves = releves.exclude(pk=exclure.pk)
    return [
        (pleins.order_by(), 'kilometrage_releve', 'date_plein', 'plein'),
        (releves.order_by(), 'kilometrage', 'date_releve', 'relevé'),
    ]


def controler_km(vehicule, km, date, champ, exclure=None):
    """Refuse un kilométrage inférieur à une saisie d'un jour précédent ou
    supérieur à une saisie d'un jour suivant (même jour : pas de contrôle)."""
    if km is None or date is None or vehicule is None:
        return
    for qs, f_km, f_date, libelle in _sources(vehicule, exclure):
        avant = qs.filter(**{f'{f_date}__lt': date, f'{f_km}__gt': km}).order_by(f'-{f_km}').first()
        if avant:
            raise serializers.ValidationError({champ: (
                f"Kilométrage inférieur à celui du {libelle} du {getattr(avant, f_date):%d/%m/%Y} "
                f"({getattr(avant, f_km):,} km). Si cette saisie est erronée, corrigez-la d'abord."
            ).replace(',', ' ')})
        apres = qs.filter(**{f'{f_date}__gt': date, f'{f_km}__lt': km}).order_by(f_km).first()
        if apres:
            raise serializers.ValidationError({champ: (
                f"Kilométrage supérieur à celui du {libelle} du {getattr(apres, f_date):%d/%m/%Y} "
                f"({getattr(apres, f_km):,} km). Si cette saisie est erronée, corrigez-la d'abord."
            ).replace(',', ' ')})


def recalculer_kilometrage(vehicule):
    """Compteur = max(kilométrage d'entrée, relevés, pleins)."""
    if vehicule is None:
        return
    km = vehicule.kilometrage_initial or 0
    for qs, f_km, _, _ in _sources(vehicule):
        km = max(km, qs.aggregate(m=Max(f_km))['m'] or 0)
    if km != vehicule.kilometrage_actuel:
        vehicule.kilometrage_actuel = km
        vehicule.save(update_fields=['kilometrage_actuel'])


def recalculer_consommations(vehicule, depuis):
    """Recalcule km de départ et consommation des pleins du véhicule datés
    à partir de `depuis` (chaque plein dépend du précédent). Le statut de
    validation n'est pas modifié."""
    from apps.carburant.models import PleinsCarburant
    if vehicule is None or depuis is None:
        return
    pleins = list(PleinsCarburant.objects.filter(vehicule=vehicule)
                  .order_by('date_plein', 'heure_plein', 'created_at'))
    precedent = None
    for p in pleins:
        if p.date_plein >= depuis:
            depart = precedent.kilometrage_releve if precedent else None
            conso = None
            if precedent and p.kilometrage_releve > precedent.kilometrage_releve:
                conso = round(float(p.volume_litres) / (p.kilometrage_releve - precedent.kilometrage_releve) * 100, 2)
            ancienne = float(p.consommation_calculee) if p.consommation_calculee is not None else None
            if p.kilometrage_depart != depart or ancienne != conso:
                PleinsCarburant.objects.filter(pk=p.pk).update(kilometrage_depart=depart, consommation_calculee=conso)
        precedent = p


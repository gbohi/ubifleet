"""UbiFleet — Cohérence du kilométrage d'un véhicule.

Le compteur d'un véhicule est déduit de ses saisies : c'est le plus grand
kilométrage parmi ses relevés et ses pleins, sans descendre sous son
kilométrage d'entrée dans le parc. Il est recalculé après chaque saisie,
correction ou suppression, de sorte qu'une erreur corrigée ne laisse pas
le compteur faussé.

Un kilométrage saisi est contrôlé par rapport aux saisies voisines (jours
précédents et suivants), et non par rapport au compteur actuel : on peut
ainsi corriger une valeur trop élevée ou saisir un relevé antérieur.
Le même jour, les saisies sont comparées selon leur heure, quand les deux
en ont une (les relevés antérieurs à l'heure obligatoire n'en ont pas).
"""

from django.db.models import Max, Q
from django.utils import timezone
from rest_framework import serializers


def heure_par_defaut(date):
    """Heure d'un relevé saisi sans heure : l'heure du serveur s'il est du
    jour même, sinon aucune (on ne l'invente pas pour une date passée)."""
    if date != timezone.localdate():
        return None
    return timezone.localtime().time().replace(second=0, microsecond=0)


def _sources(vehicule, exclure=None):
    """(queryset, champ km, champ date, champ heure, libellé) des saisies kilométriques du véhicule.
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
        (pleins.order_by(), 'kilometrage_releve', 'date_plein', 'heure_plein', 'plein'),
        (releves.order_by(), 'kilometrage', 'date_releve', 'heure_releve', 'relevé'),
    ]


def _quand(obj, f_date, f_heure):
    d, h = getattr(obj, f_date), getattr(obj, f_heure)
    return f"{d:%d/%m/%Y}" + (f" à {h:%H:%M}" if h else '')


def controler_km(vehicule, km, date, champ, exclure=None, heure=None):
    """Refuse un kilométrage inférieur à une saisie antérieure ou supérieur à
    une saisie postérieure. Le même jour, seules les saisies ayant une heure
    sont comparées, et seulement si `heure` est connue."""
    if km is None or date is None or vehicule is None:
        return
    for qs, f_km, f_date, f_heure, libelle in _sources(vehicule, exclure):
        anterieur = Q(**{f'{f_date}__lt': date})
        posterieur = Q(**{f'{f_date}__gt': date})
        if heure is not None:
            anterieur |= Q(**{f_date: date, f'{f_heure}__lt': heure})
            posterieur |= Q(**{f_date: date, f'{f_heure}__gt': heure})
        avant = qs.filter(anterieur, **{f'{f_km}__gt': km}).order_by(f'-{f_km}').first()
        if avant:
            raise serializers.ValidationError({champ: (
                f"Kilométrage inférieur à celui du {libelle} du {_quand(avant, f_date, f_heure)} "
                f"({getattr(avant, f_km):,} km). Si cette saisie est erronée, corrigez-la d'abord."
            ).replace(',', ' ')})
        apres = qs.filter(posterieur, **{f'{f_km}__lt': km}).order_by(f_km).first()
        if apres:
            raise serializers.ValidationError({champ: (
                f"Kilométrage supérieur à celui du {libelle} du {_quand(apres, f_date, f_heure)} "
                f"({getattr(apres, f_km):,} km). Si cette saisie est erronée, corrigez-la d'abord."
            ).replace(',', ' ')})


def recalculer_kilometrage(vehicule):
    """Compteur = max(kilométrage d'entrée, relevés, pleins)."""
    if vehicule is None:
        return
    km = vehicule.kilometrage_initial or 0
    for qs, f_km, *_ in _sources(vehicule):
        km = max(km, qs.aggregate(m=Max(f_km))['m'] or 0)
    if km != vehicule.kilometrage_actuel:
        vehicule.kilometrage_actuel = km
        vehicule.save(update_fields=['kilometrage_actuel'])


def recalculer_consommations(vehicule, depuis):
    """Recalcule km de départ, consommation et anomalie des pleins du véhicule
    datés à partir de `depuis` (chaque plein dépend du précédent)."""
    from apps.carburant.models import PleinsCarburant, motif_anomalie
    if vehicule is None or depuis is None:
        return
    pleins = list(PleinsCarburant.objects.filter(vehicule=vehicule)
                  .order_by('date_plein', 'heure_plein', 'created_at'))
    moyenne = vehicule.consommation_moyenne()
    S = PleinsCarburant.StatutValidation
    precedent = None
    for p in pleins:
        if p.date_plein >= depuis:
            depart = precedent.kilometrage_releve if precedent else None
            conso = None
            if precedent and p.kilometrage_releve > precedent.kilometrage_releve:
                conso = round(float(p.volume_litres) / (p.kilometrage_releve - precedent.kilometrage_releve) * 100, 2)
            ancienne = float(p.consommation_calculee) if p.consommation_calculee is not None else None
            statut, motif = p.statut_validation, p.motif_anomalie
            if statut != S.REJETE:
                motif = motif_anomalie(vehicule, conso, moyenne)
                statut = S.ANOMALIE if motif else S.VALIDE
            if (p.kilometrage_depart, ancienne, p.statut_validation, p.motif_anomalie) != (depart, conso, statut, motif):
                PleinsCarburant.objects.filter(pk=p.pk).update(
                    kilometrage_depart=depart, consommation_calculee=conso,
                    statut_validation=statut, motif_anomalie=motif)
        precedent = p


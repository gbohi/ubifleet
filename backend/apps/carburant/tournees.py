"""UbiFleet — Tournées effectuées : ouverture, rattachement des prises, clôture.

Une tournée effectuée est ouverte par la première prise de carburant de type
« tournée » d'un véhicule qui n'a pas de tournée en cours ; les prises
suivantes du véhicule s'y rattachent jusqu'à la clôture. Un véhicule n'a
qu'une tournée en cours à la fois : pour une prise d'un autre type, il faut
d'abord la clôturer.

Clôture : KM retour (au moins celui de la dernière prise). S'il le dépasse,
un relevé kilométrique de retour (type « tournée ») est créé pour que le
compteur du véhicule reste juste. Les droits Clôturer / Rouvrir / Annuler
sont des actions du module carburant (Administration › Permissions).
"""

from datetime import time as datetime_time

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

ACTION_CLOTURER, ACTION_ROUVRIR, ACTION_ANNULER = 'cloturer_tournee', 'rouvrir_tournee', 'annuler_tournee'
DROITS_PAR_DEFAUT = {ACTION_CLOTURER: 'operateur', ACTION_ROUVRIR: 'responsable_flotte',
                     ACTION_ANNULER: 'responsable_flotte'}


def a_le_droit(user, action):
    """Droit de l'utilisateur (règle en base, sinon niveau par défaut)."""
    from types import SimpleNamespace
    from apps.accounts.permissions import action_autorisee
    vue = SimpleNamespace(module='carburant', role_map=DROITS_PAR_DEFAUT)
    return action_autorisee(user, vue, action)


def exiger_droit(user, action, libelle):
    if not a_le_droit(user, action):
        raise PermissionDenied(f"Vous n'avez pas le droit de {libelle} une tournée "
                               "(Administration › Permissions, module Carburant).")


def droits(user):
    return {'cloturer': a_le_droit(user, ACTION_CLOTURER),
            'rouvrir': a_le_droit(user, ACTION_ROUVRIR),
            'annuler': a_le_droit(user, ACTION_ANNULER)}


def quand(d, h):
    return f"{d:%d/%m/%Y}" + (f" à {h:%H:%M}" if h else '')


def en_cours(vehicule, exclure=None):
    from .models import TourneeEffectuee
    if vehicule is None:
        return None
    qs = TourneeEffectuee.objects.filter(vehicule=vehicule, statut=TourneeEffectuee.Statut.EN_COURS)
    if exclure is not None:
        qs = qs.exclude(pk=exclure.pk)
    return qs.select_related('tournee').first()


def dotation_au(tournee, date):
    """Dotation de la tournée en vigueur à une date (historique des changements
    approuvés), sinon la dotation actuelle."""
    from apps.parametrage.models import ChangementDotation
    S = ChangementDotation.Statut
    changements = (ChangementDotation.objects
                   .filter(tournee=tournee, statut__in=[S.INITIALE, S.APPROUVEE])
                   .order_by('created_at'))
    valeur = None
    for c in changements:
        jour = (c.date_decision or c.created_at)
        if timezone.localtime(jour).date() <= date:
            valeur = c.nouvelle_dotation
    return valeur if valeur is not None else tournee.dotation


def numero_suivant(tournee, annee):
    from .models import TourneeEffectuee
    prefixe = f"{tournee.code}-{annee}-"
    n = TourneeEffectuee.objects.filter(numero__startswith=prefixe).count() + 1
    while TourneeEffectuee.objects.filter(numero=f"{prefixe}{n:04d}").exists():
        n += 1
    return f"{prefixe}{n:04d}"


def ouvrir(prise, user=None):
    """Ouvre une tournée effectuée à partir de sa première prise."""
    from .models import TourneeEffectuee
    t = prise.tournee
    te = TourneeEffectuee.objects.create(
        numero=numero_suivant(t, prise.date_plein.year), tournee=t,
        vehicule=prise.vehicule, chauffeur=prise.chauffeur, agence=prise.agence,
        date_debut=prise.date_plein, heure_debut=prise.heure_plein, km_depart=prise.kilometrage_releve,
        dotation_theorique=dotation_au(t, prise.date_plein), km_theorique=t.km_theorique or 0,
        created_by=user,
    )
    prise.tournee_effectuee = te
    prise.save(update_fields=['tournee_effectuee'])
    return te


def prises_ordonnees(te):
    from .anomalies import ordre_chronologique
    return sorted(te.prises.all(), key=ordre_chronologique)


def actualiser(te):
    """Début, KM départ (et KM retour sans relevé de retour) d'après les
    prises ; une tournée sans prise disparaît."""
    if te is None or te.statut == te.Statut.ANNULEE:
        return
    prises = prises_ordonnees(te)
    if not prises:
        if te.releve_retour_id:
            te.releve_retour.delete()
        te.delete()
        return
    premiere, derniere = prises[0], prises[-1]
    te.date_debut, te.heure_debut, te.km_depart = premiere.date_plein, premiere.heure_plein, premiere.kilometrage_releve
    if te.statut == te.Statut.CLOTUREE and not te.releve_retour_id:
        te.km_retour = derniere.kilometrage_releve
        te.date_fin, te.heure_fin = derniere.date_plein, derniere.heure_plein
    te.save()


def actualiser_par_id(pk):
    from .models import TourneeEffectuee
    if pk:
        actualiser(TourneeEffectuee.objects.filter(pk=pk).select_related('releve_retour').first())


@transaction.atomic
def cloturer(te, user, km_retour=None, date_fin=None, heure_fin=None, commentaire=''):
    from apps.parametrage.fenetre_saisie import RELEVES, fenetre
    from apps.parametrage.models import TypeMouvement
    from apps.vehicules.kilometrage import controler_km, recalculer_kilometrage
    from apps.vehicules.models import ReleveKilometrage

    exiger_droit(user, ACTION_CLOTURER, 'clôturer')
    if te.statut != te.Statut.EN_COURS:
        raise serializers.ValidationError({'detail': "Cette tournée n'est pas en cours."})
    derniere = prises_ordonnees(te)[-1]
    km_retour = derniere.kilometrage_releve if km_retour in (None, '') else int(km_retour)
    if km_retour < derniere.kilometrage_releve:
        raise serializers.ValidationError({'km_retour': (
            f"Le KM retour ne peut pas être inférieur au kilométrage de la dernière prise "
            f"({derniere.kilometrage_releve:,} km le {quand(derniere.date_plein, derniere.heure_plein)}).")
            .replace(',', ' ')})

    if km_retour == derniere.kilometrage_releve and date_fin is None:
        # Clôture à la dernière prise : pas de relevé supplémentaire
        date_fin, heure_fin = derniere.date_plein, derniere.heure_plein
    else:
        maintenant = timezone.localtime()
        date_fin = date_fin or maintenant.date()
        heure_fin = heure_fin or (maintenant.time().replace(second=0, microsecond=0)
                                  if date_fin == maintenant.date() else None)
        fin = (date_fin, heure_fin or datetime_time.max)
        if fin < (derniere.date_plein, derniere.heure_plein or datetime_time.min):
            raise serializers.ValidationError({'date_fin': (
                "La fin de la tournée ne peut pas précéder sa dernière prise "
                f"({quand(derniere.date_plein, derniere.heure_plein)}).")})
    if km_retour > derniere.kilometrage_releve:
        hors_delai = fenetre(user, RELEVES).controler_date(date_fin, 'date_fin')
        controler_km(te.vehicule, km_retour, date_fin, 'km_retour', heure=heure_fin)
        releve = ReleveKilometrage.objects.create(
            vehicule=te.vehicule, kilometrage=km_retour, date_releve=date_fin, heure_releve=heure_fin,
            type_mouvement=TypeMouvement.CODE_TOURNEE, tournee=te.tournee, chauffeur=te.chauffeur,
            notes=f"Retour de la tournée n° {te.numero}", created_by=user,
            **({'saisie_hors_delai': True, 'hors_delai_par': user, 'hors_delai_le': timezone.now()}
               if hors_delai else {}),
        )
        te.releve_retour = releve
        recalculer_kilometrage(te.vehicule)

    te.statut = te.Statut.CLOTUREE
    te.km_retour, te.date_fin, te.heure_fin = km_retour, date_fin, heure_fin
    te.cloturee_par, te.cloturee_le = user, timezone.now()
    if commentaire:
        te.commentaire = commentaire
    te.save()
    return te


@transaction.atomic
def rouvrir(te, user):
    from apps.vehicules.kilometrage import recalculer_kilometrage
    exiger_droit(user, ACTION_ROUVRIR, 'rouvrir')
    if te.statut != te.Statut.CLOTUREE:
        raise serializers.ValidationError({'detail': "Seule une tournée clôturée peut être rouverte."})
    autre = en_cours(te.vehicule, exclure=te)
    if autre:
        raise serializers.ValidationError({'detail': (
            f"Le véhicule a déjà une tournée en cours ({autre.tournee.code}, n° {autre.numero}) : "
            "clôturez-la avant de rouvrir celle-ci.")})
    if te.releve_retour_id:
        te.releve_retour.delete()
        te.releve_retour = None
        recalculer_kilometrage(te.vehicule)
    te.statut = te.Statut.EN_COURS
    te.km_retour = te.date_fin = te.heure_fin = te.cloturee_par = te.cloturee_le = None
    te.save()
    return te


@transaction.atomic
def annuler(te, user, type_mouvement, motif):
    """Tournée ouverte par erreur : ses prises passent dans un autre type de
    mouvement (hors tournée) et la tournée est marquée annulée."""
    from apps.parametrage.models import TypeMouvement
    exiger_droit(user, ACTION_ANNULER, 'annuler')
    if te.statut != te.Statut.EN_COURS:
        raise serializers.ValidationError({'detail': "Seule une tournée en cours peut être annulée."})
    if not (motif or '').strip():
        raise serializers.ValidationError({'motif': "Le motif de l'annulation est obligatoire."})
    t = TypeMouvement.objects.filter(code=type_mouvement, actif=True, pour_prises=True).first()
    if t is None or t.code == TypeMouvement.CODE_TOURNEE:
        raise serializers.ValidationError({'type_mouvement': (
            "Choisissez le type de mouvement (hors tournée) à donner aux prises de cette tournée.")})
    te.prises.update(type_mouvement=t.code, tournee=None, tournee_effectuee=None)
    te.statut = te.Statut.ANNULEE
    te.motif_annulation = motif.strip()
    te.cloturee_par, te.cloturee_le = user, timezone.now()
    te.save()
    return te

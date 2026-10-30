"""UbiFleet — Correction des pleins et relevés kilométriques.

Règles communes aux deux saisies (mixin de vue) :
- fenêtre de saisie : une donnée figée ne se corrige qu'avec le droit
  « Saisie hors délai », et un motif est alors obligatoire ;
- l'auteur d'une saisie peut la corriger ou la supprimer tant qu'elle est
  dans la fenêtre, même si son rôle n'a pas ce droit ;
- chaque modification ou suppression est journalisée (CorrectionSaisie) ;
- le compteur du véhicule et les consommations sont recalculés.
"""

from datetime import time

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from apps.core.agences import controler_agence
from .fenetre_saisie import fenetre, tracer_hors_delai
from .models import CorrectionSaisie

ACTIONS_CORRECTION = ('update', 'partial_update', 'destroy')


def _lisible(obj, champ):
    f = obj._meta.get_field(champ)
    v = getattr(obj, champ)
    if v is None or v == '':
        return None
    if f.is_relation:
        return str(v)
    if hasattr(v, 'name'):              # fichier
        return v.name.rsplit('/', 1)[-1] if v.name else None
    if isinstance(v, time):
        return v.strftime('%H:%M')
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return str(v)


def instantane(obj, champs):
    return {c: _lisible(obj, c) for c in champs}


def changements(obj, champs, avant, apres):
    return [
        {'champ': c, 'libelle': str(obj._meta.get_field(c).verbose_name).capitalize(),
         'avant': avant.get(c), 'apres': apres.get(c) if apres is not None else None}
        for c in champs
        if apres is None and avant.get(c) is not None or apres is not None and avant.get(c) != apres.get(c)
    ]


class SaisieCorrigeableMixin:
    """À placer avant ModelViewSet. Définir domaine_saisie, champ_date et
    champs_journal (champs suivis dans le journal)."""
    domaine_saisie = None
    champ_date = None
    champs_journal = ()

    # ── Droits : l'auteur peut corriger sa saisie dans la fenêtre ────────
    def check_permissions(self, request):
        self._auteur_seulement = False
        try:
            super().check_permissions(request)
        except (PermissionDenied, NotAuthenticated):
            if self.action not in ACTIONS_CORRECTION or not request.user.is_authenticated:
                raise
            self._auteur_seulement = True     # vérifié sur l'objet

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if getattr(self, '_auteur_seulement', False):
            f = fenetre(request.user, self.domaine_saisie)
            if obj.created_by_id != request.user.id or not f.dans_fenetre(getattr(obj, self.champ_date)):
                self.permission_denied(request, message=(
                    "Vous ne pouvez corriger ou supprimer que vos propres saisies, "
                    "tant qu'elles sont dans la fenêtre de saisie."))

    # ── Motif ─────────────────────────────────────────────────────────
    def motif_correction(self, hors_delai):
        motif = (self.request.data.get('motif_correction')
                 or self.request.query_params.get('motif') or '').strip()
        if hors_delai and not motif:
            raise serializers.ValidationError(
                {'motif_correction': "Un motif est obligatoire pour corriger une saisie hors délai."})
        return motif

    def journaliser(self, obj, action, avant, apres, hors_delai, motif):
        CorrectionSaisie.objects.create(
            domaine=self.domaine_saisie, objet_id=obj.pk, libelle=str(obj)[:200],
            vehicule_id=obj.vehicule_id, action=action, auteur=self.request.user,
            hors_delai=hors_delai, motif=motif,
            changements=changements(obj, self.champs_journal, avant, apres),
        )

    def apres_correction(self, vehicules, dates):
        """Recalcul du compteur et des consommations des véhicules touchés."""
        from apps.vehicules.kilometrage import recalculer_consommations, recalculer_kilometrage
        depuis = min(d for d in dates if d)
        for v in {v.pk: v for v in vehicules if v}.values():
            v.refresh_from_db()
            recalculer_kilometrage(v)
            recalculer_consommations(v, depuis)

    # ── Modification / suppression ───────────────────────────────────
    @transaction.atomic
    def perform_update(self, serializer):
        user, inst, data = self.request.user, serializer.instance, serializer.validated_data
        controler_agence(user, data)
        f = fenetre(user, self.domaine_saisie)
        date_avant = getattr(inst, self.champ_date)
        hors_delai = f.controler_modification(date_avant)
        if self.champ_date in data:
            hors_delai = f.controler_date(data[self.champ_date], self.champ_date) or hors_delai
        motif = self.motif_correction(hors_delai)
        avant = instantane(inst, self.champs_journal)
        vehicule_avant = inst.vehicule
        obj = serializer.save(**(tracer_hors_delai(user) if hors_delai else {}))
        apres = instantane(obj, self.champs_journal)
        if avant != apres or motif:
            self.journaliser(obj, CorrectionSaisie.Action.MODIFICATION, avant, apres, hors_delai, motif)
        self.apres_correction([vehicule_avant, obj.vehicule], [date_avant, getattr(obj, self.champ_date)])

    @transaction.atomic
    def perform_destroy(self, instance):
        f = fenetre(self.request.user, self.domaine_saisie)
        hors_delai = f.controler_modification(getattr(instance, self.champ_date))
        motif = self.motif_correction(hors_delai)
        self.journaliser(instance, CorrectionSaisie.Action.SUPPRESSION,
                         instantane(instance, self.champs_journal), None, hors_delai, motif)
        vehicule, d = instance.vehicule, getattr(instance, self.champ_date)
        instance.delete()
        self.apres_correction([vehicule], [d])

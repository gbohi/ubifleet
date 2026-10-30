"""Recalcule consommation et anomalie de toutes les prises de carburant.

À lancer après le déploiement de la nouvelle détection des anomalies, ou
après un changement du seuil (Paramètres › Seuils), qui ne s'applique
sinon qu'aux saisies et corrections suivantes. N'ouvre aucune alerte, sauf
avec --alertes (alerte pour chaque prise anormale datée d'au moins
--depuis)."""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.carburant.anomalies import evaluer, prises_du_vehicule, statut_et_motif, synchroniser_alerte
from apps.carburant.models import PleinsCarburant
from apps.vehicules.models import Vehicule


class Command(BaseCommand):
    help = "Recalcule consommation et anomalie des prises de carburant (sans alerte par défaut)."

    def add_arguments(self, parser):
        parser.add_argument('--alertes', action='store_true',
                            help="Ouvrir l'alerte des prises anormales récentes (cf. --depuis).")
        parser.add_argument('--depuis', type=int, default=30,
                            help="Avec --alertes : prises des N derniers jours (défaut 30).")

    @transaction.atomic
    def handle(self, *args, **opts):
        limite = timezone.localdate() - datetime.timedelta(days=opts['depuis'])
        modifiees = anomalies = alertes = 0
        for vehicule in Vehicule.objects.filter(pleins__isnull=False).distinct():
            prises = prises_du_vehicule(vehicule)
            evaluations = evaluer(prises)
            for p in prises:
                ev = evaluations[p.pk]
                statut, motif = statut_et_motif(p, ev)
                ancienne = float(p.consommation_calculee) if p.consommation_calculee is not None else None
                if (p.kilometrage_depart, ancienne, p.statut_validation, p.motif_anomalie) != (ev.depart, ev.conso, statut, motif):
                    PleinsCarburant.objects.filter(pk=p.pk).update(
                        kilometrage_depart=ev.depart, consommation_calculee=ev.conso,
                        statut_validation=statut, motif_anomalie=motif)
                    p.statut_validation, p.motif_anomalie = statut, motif
                    modifiees += 1
                anomalies += statut == PleinsCarburant.StatutValidation.ANOMALIE
                if opts['alertes'] and p.date_plein >= limite:
                    synchroniser_alerte(p, ev)
                    alertes += statut == PleinsCarburant.StatutValidation.ANOMALIE
        self.stdout.write(self.style.SUCCESS(
            f"{modifiees} prise(s) mise(s) à jour ; {anomalies} prise(s) en anomalie"
            + (f" ; {alertes} alerte(s) ouverte(s) ou à jour." if opts['alertes'] else ".")))

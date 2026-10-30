"""UbiFleet — Modification de la dotation des tournées par circuit de validation."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import ChangementDotation, Tournee

CODE_TYPE_DEMANDE = 'dotation'


@transaction.atomic
def demander_modification(tournee: Tournee, nouvelle: int, motif: str, utilisateur) -> ChangementDotation:
    """Crée la demande de modification et la soumet au circuit « dotation »."""
    from apps.demandes.models import Demande, TypeDemande
    from apps.demandes import workflow

    tournee = Tournee.objects.select_for_update().get(pk=tournee.pk)
    if nouvelle == tournee.dotation:
        raise ValidationError({'nouvelle_dotation': 'La nouvelle dotation est identique à la dotation actuelle.'})
    if tournee.changements_dotation.filter(statut=ChangementDotation.Statut.EN_ATTENTE).exists():
        raise ValidationError({'detail': 'Une modification de dotation est déjà en attente de validation pour cette tournée.'})
    type_demande = TypeDemande.objects.filter(code=CODE_TYPE_DEMANDE, actif=True).first()
    if type_demande is None or not type_demande.niveaux.exists():
        raise ValidationError({'detail': "Le circuit « Modification de dotation » n'est pas configuré "
                                         "(Paramètres › Circuits de validation)."})

    demande = Demande.objects.create(
        type_demande=type_demande, demandeur=utilisateur, created_by=utilisateur,
        agence=tournee.agence,
        titre=f'Dotation tournée {tournee.code} : {tournee.dotation} L → {nouvelle} L',
        description=(f'Tournée {tournee.code} — {tournee.libelle}\n'
                     f'Dotation actuelle : {tournee.dotation} L\n'
                     f'Dotation demandée : {nouvelle} L\n\nMotif : {motif or "—"}'),
    )
    changement = ChangementDotation.objects.create(
        tournee=tournee, ancienne_dotation=tournee.dotation, nouvelle_dotation=nouvelle,
        motif=motif, demandeur=utilisateur, demande=demande,
    )
    workflow.soumettre(demande)
    return changement


def appliquer_decision(sender, demande, decision, utilisateur, **kwargs):
    """Récepteur de demande_cloturee : applique ou clôt le changement lié."""
    changement = (ChangementDotation.objects.select_for_update()
                  .filter(demande=demande, statut=ChangementDotation.Statut.EN_ATTENTE).first())
    if changement is None:
        return
    changement.statut = {
        'approuvee': ChangementDotation.Statut.APPROUVEE,
        'rejetee':   ChangementDotation.Statut.REJETEE,
        'annulee':   ChangementDotation.Statut.ANNULEE,
    }[decision]
    changement.decide_par = utilisateur
    changement.date_decision = timezone.now()
    changement.save()
    if decision == 'approuvee':
        Tournee.objects.filter(pk=changement.tournee_id).update(
            dotation=changement.nouvelle_dotation, updated_at=timezone.now())

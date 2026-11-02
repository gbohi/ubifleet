"""UbiFleet — Alertes Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class Alerte(UbiFleetBaseModel):
    class TypeAlerte(models.TextChoices):
        REVISION_DUE = 'revision_due', 'Révision due'
        ASSURANCE_EXPIRATION = 'assurance_exp', "Assurance expirant bientôt"
        ASSURANCE_EXPIREE = 'assurance_expiree', 'Assurance expirée'
        CONSO_ANORMALE = 'conso_anormale', 'Consommation anormale'
        CT_EXPIRATION = 'ct_exp', 'Contrôle technique expirant'
        CT_EXPIREE = 'ct_expiree', 'Contrôle technique expiré'
        PERMIS_EXPIRATION = 'permis_exp', 'Permis expirant bientôt'
        PERMIS_EXPIRE = 'permis_expire', 'Permis expiré'
        BUDGET_DEPASSE = 'budget_depasse', 'Budget dépassé'
        PNEU_USURE = 'pneu_usure', 'Pneu à changer'
        PLEIN_ANOMALIE = 'plein_anomalie', 'Anomalie prise de carburant'
        SINISTRE_OUVERT = 'sinistre_ouvert', 'Sinistre en attente de traitement'
        DEMANDE_A_VALIDER = 'demande_a_valider', 'Demande à valider'
        TOURNEE_OUVERTE = 'tournee_ouverte', 'Tournée non clôturée'
        VISITE_MEDICALE_EXPIRATION = 'visite_med_exp', 'Visite médicale expirant bientôt'
        VISITE_MEDICALE_EXPIREE = 'visite_med_expiree', 'Visite médicale expirée'
        CONTRAT_EXPIRATION = 'contrat_exp', 'Contrat de travail expirant bientôt'
        CONTRAT_EXPIRE = 'contrat_expire', 'Contrat de travail expiré'

    class Priorite(models.TextChoices):
        CRITIQUE = 'critique', 'Critique'
        HAUTE = 'haute', 'Haute'
        NORMALE = 'normale', 'Normale'
        BASSE = 'basse', 'Basse'

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        LUE = 'lue', 'Lue'
        TRAITEE = 'traitee', 'Traitée'
        IGNOREE = 'ignoree', 'Ignorée'

    type_alerte = models.CharField(max_length=25, choices=TypeAlerte.choices)
    priorite = models.CharField(max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIVE)

    titre = models.CharField(max_length=200)
    message = models.TextField()

    vehicule = models.ForeignKey(
        'vehicules.Vehicule', null=True, blank=True,
        on_delete=models.CASCADE, related_name='alertes'
    )
    chauffeur = models.ForeignKey(
        'chauffeurs.Chauffeur', null=True, blank=True,
        on_delete=models.CASCADE, related_name='alertes'
    )
    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.CASCADE,
        related_name='alertes'
    )
    # Prise de carburant à l'origine d'une alerte « Consommation anormale »
    plein = models.ForeignKey(
        'carburant.PleinsCarburant', null=True, blank=True,
        on_delete=models.CASCADE, related_name='alertes',
        verbose_name='Prise de carburant'
    )
    # Tournée effectuée restée ouverte trop longtemps
    tournee_effectuee = models.ForeignKey(
        'carburant.TourneeEffectuee', null=True, blank=True,
        on_delete=models.CASCADE, related_name='alertes',
        verbose_name='Tournée effectuée'
    )

    date_echeance = models.DateField(null=True, blank=True)
    destinataire  = models.ForeignKey(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='alertes_recues',
        help_text="Utilisateur destinataire de l'alerte (ex: validateur d'une demande)"
    )
    traitee_par = models.ForeignKey(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='alertes_traitees'
    )
    date_traitement = models.DateTimeField(null=True, blank=True)
    notes_traitement = models.TextField(blank=True)

    class Meta:
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_priorite_display()}] {self.titre}"

"""UbiFleet — Entretien Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class TypeIntervention(UbiFleetBaseModel):
    """Catalogue des types d'interventions."""
    nom = models.CharField(max_length=150)
    categorie = models.CharField(
        max_length=20,
        choices=[
            ('preventif', 'Entretien préventif'),
            ('curatif', 'Réparation curative'),
            ('pneus', 'Pneus'),
            ('carrosserie', 'Carrosserie'),
            ('controle', 'Contrôle réglementaire'),
            ('autre', 'Autre'),
        ],
        default='preventif'
    )
    periodicite_km = models.PositiveIntegerField(
        default=0,
        help_text="Périodicité en km (0 = pas de périodicité)"
    )
    periodicite_mois = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Type d'intervention"
        ordering = ['categorie', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.get_categorie_display()})"


class Prestataire(UbiFleetBaseModel):
    """Garage / prestataire d'entretien."""
    nom = models.CharField(max_length=150)
    specialite = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    agence = models.ForeignKey(
        'accounts.Agence', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='prestataires'
    )
    note_qualite = models.DecimalField(
        max_digits=3, decimal_places=1,
        null=True, blank=True,
        help_text="Note /5"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Prestataire / Garage"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Intervention(UbiFleetBaseModel):
    """Intervention de maintenance sur un véhicule."""

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'
        EN_ATTENTE_PIECE = 'attente_piece', 'En attente de pièces'

    class Priorite(models.TextChoices):
        CRITIQUE = 'critique', 'Critique'
        HAUTE = 'haute', 'Haute'
        NORMALE = 'normale', 'Normale'
        BASSE = 'basse', 'Basse'

    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.CASCADE,
        related_name='interventions'
    )
    type_intervention = models.ForeignKey(
        TypeIntervention, on_delete=models.PROTECT,
        related_name='interventions'
    )
    prestataire = models.ForeignKey(
        Prestataire, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='interventions'
    )

    # Planification
    date_planifiee = models.DateField(verbose_name="Date planifiée")
    date_debut = models.DateField(null=True, blank=True, verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")

    # Kilométrage
    kilometrage_intervention = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Kilométrage à l'intervention"
    )
    prochain_km = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Prochain entretien (km)"
    )

    # Coûts
    cout_estime = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Coût estimé (FCFA)"
    )
    cout_reel = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Coût réel (FCFA)"
    )

    # Statut
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.PLANIFIE
    )
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices,
        default=Priorite.NORMALE
    )

    # Détails
    description = models.TextField(blank=True, verbose_name="Description des travaux")
    rapport_intervention = models.TextField(blank=True, verbose_name="Rapport technique")
    facture = models.FileField(
        upload_to='entretien/factures/', null=True, blank=True
    )
    bon_travail = models.FileField(
        upload_to='entretien/bons/', null=True, blank=True
    )

    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.PROTECT,
        related_name='interventions'
    )

    class Meta:
        verbose_name = "Intervention"
        verbose_name_plural = "Interventions"
        ordering = ['-date_planifiee']

    def __str__(self):
        return (
            f"{self.vehicule.immatriculation} — "
            f"{self.type_intervention.nom} — {self.date_planifiee}"
        )

    def save(self, *args, **kwargs):
        if self.statut == self.Statut.TERMINE and self.prochain_km:
            self.vehicule.kilometrage_revision = self.prochain_km
            self.vehicule.save(update_fields=['kilometrage_revision'])
        super().save(*args, **kwargs)


class SuiviPneus(UbiFleetBaseModel):
    """Suivi des pneus par véhicule."""

    class Position(models.TextChoices):
        AV_GAUCHE = 'av_gauche', 'Avant gauche'
        AV_DROIT = 'av_droit', 'Avant droit'
        AR_GAUCHE = 'ar_gauche', 'Arrière gauche'
        AR_DROIT = 'ar_droit', 'Arrière droit'
        SECOURS = 'secours', 'Roue de secours'

    class Statut(models.TextChoices):
        EN_SERVICE = 'en_service', 'En service'
        A_CHANGER = 'a_changer', 'À changer'
        CHANGE = 'change', 'Changé'

    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.CASCADE,
        related_name='pneus'
    )
    position = models.CharField(max_length=15, choices=Position.choices)
    marque = models.CharField(max_length=60, blank=True)
    dimension = models.CharField(max_length=30, blank=True, help_text="ex: 195/65 R15")
    date_montage = models.DateField()
    kilometrage_montage = models.PositiveIntegerField(default=0)
    kilometrage_remplacement = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Km prévu pour remplacement"
    )
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.EN_SERVICE
    )
    cout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Pneu"
        verbose_name_plural = "Pneus"
        ordering = ['vehicule', 'position']

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.get_position_display()}"

    @property
    def kilometrage_utilise(self):
        return self.vehicule.kilometrage_actuel - self.kilometrage_montage

    @property
    def usure_pct(self):
        if self.kilometrage_remplacement and self.kilometrage_montage:
            duree_prevue = self.kilometrage_remplacement - self.kilometrage_montage
            if duree_prevue > 0:
                return min(round((self.kilometrage_utilise / duree_prevue) * 100, 1), 100)
        return None


class DocumentIntervention(models.Model):
    """Documents attachés à une intervention (planification ou clôture)."""

    class TypeDocument(models.TextChoices):
        PLANIFICATION = 'planification', 'Document de planification'
        CLOTURE       = 'cloture',       'Rapport de clôture'
        AUTRE         = 'autre',         'Autre document'

    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE,
        related_name='documents'
    )
    fichier      = models.FileField(upload_to='entretien/documents/')
    nom          = models.CharField(max_length=255, blank=True)
    type_doc     = models.CharField(
        max_length=20, choices=TypeDocument.choices,
        default=TypeDocument.AUTRE
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Document intervention'
        verbose_name_plural = 'Documents intervention'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.nom or self.fichier.name} — {self.intervention}"

    def save(self, *args, **kwargs):
        if not self.nom and self.fichier:
            import os
            self.nom = os.path.basename(self.fichier.name)
        super().save(*args, **kwargs)

"""UbiFleet — Sinistres & Assurances Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class Assureur(UbiFleetBaseModel):
    nom = models.CharField(max_length=150)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    contact_sinistre = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Assureur"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class ContratAssurance(UbiFleetBaseModel):
    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.CASCADE,
        related_name='contrats_assurance'
    )
    assureur = models.ForeignKey(
        Assureur, on_delete=models.PROTECT,
        related_name='contrats'
    )
    numero_police = models.CharField(max_length=100)
    # Code de Paramètres › Types de contrat d'assurance
    type_contrat = models.CharField(max_length=20)
    date_debut = models.DateField()
    date_fin = models.DateField()
    prime_annuelle = models.DecimalField(max_digits=12, decimal_places=2)
    franchise = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    document = models.FileField(upload_to='assurances/contrats/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Contrat d'assurance"
        ordering = ['-date_fin']

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.assureur.nom} — {self.numero_police}"

    def get_type_contrat_display(self):
        from apps.parametrage.models import TypeContratAssurance, libelles
        return libelles(TypeContratAssurance).get(self.type_contrat, self.type_contrat)

    @property
    def est_expire(self):
        from django.utils import timezone
        return self.date_fin < timezone.now().date()

    @property
    def jours_restants(self):
        from django.utils import timezone
        delta = self.date_fin - timezone.now().date()
        return delta.days


class Sinistre(UbiFleetBaseModel):
    class Statut(models.TextChoices):
        DECLARE = 'declare', 'Déclaré'
        EN_INSTRUCTION = 'en_instruction', 'En instruction'
        EXPERTISE = 'expertise', 'En expertise'
        REPARATION = 'reparation', 'En réparation'
        INDEMNISE = 'indemnise', 'Indemnisé'
        CLOS = 'clos', 'Clos sans suite'
        CONTESTE = 'conteste', 'Contesté'

    class Responsabilite(models.TextChoices):
        TOTAL = 'total', 'Responsabilité totale'
        PARTIELLE = 'partielle', 'Responsabilité partagée'
        TIERS = 'tiers', 'Tiers responsable'
        FORCE_MAJEURE = 'force_majeure', 'Force majeure'

    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.PROTECT,
        related_name='sinistres'
    )
    contrat_assurance = models.ForeignKey(
        ContratAssurance, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sinistres'
    )
    chauffeur = models.ForeignKey(
        'chauffeurs.Chauffeur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sinistres'
    )

    # Référence
    numero_dossier = models.CharField(max_length=50, unique=True)
    # Code de Paramètres › Types de sinistre
    type_sinistre = models.CharField(max_length=20)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.DECLARE)
    responsabilite = models.CharField(
        max_length=20, choices=Responsabilite.choices,
        blank=True
    )

    # Événement
    date_sinistre = models.DateField()
    lieu = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    kilometrage_sinistre = models.PositiveIntegerField(null=True, blank=True)

    # Tiers impliqué
    tiers_immatriculation = models.CharField(max_length=20, blank=True)
    tiers_assureur = models.CharField(max_length=100, blank=True)
    tiers_nom = models.CharField(max_length=150, blank=True)

    # Financier
    dommages_estimes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cout_reparation = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    indemnisation_recue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    franchise_appliquee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Suivi
    date_declaration_assureur = models.DateField(null=True, blank=True)
    date_expertise = models.DateField(null=True, blank=True)
    date_cloture = models.DateField(null=True, blank=True)
    numero_constat = models.CharField(max_length=50, blank=True)

    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.PROTECT,
        related_name='sinistres'
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sinistre"
        verbose_name_plural = "Sinistres"
        ordering = ['-date_sinistre']

    def __str__(self):
        return f"{self.numero_dossier} — {self.vehicule.immatriculation} — {self.get_type_sinistre_display()}"

    def get_type_sinistre_display(self):
        from apps.parametrage.models import TypeSinistre, libelles
        return libelles(TypeSinistre).get(self.type_sinistre, self.type_sinistre)

    def save(self, *args, **kwargs):
        if not self.numero_dossier:
            from django.utils import timezone
            year = timezone.now().year
            last = Sinistre.objects.filter(
                numero_dossier__startswith=f'SIN-{year}-'
            ).count()
            self.numero_dossier = f'SIN-{year}-{str(last + 1).zfill(3)}'
        super().save(*args, **kwargs)


class PieceJointeSinistre(UbiFleetBaseModel):
    sinistre = models.ForeignKey(Sinistre, on_delete=models.CASCADE, related_name='pièces_jointes')
    nom = models.CharField(max_length=100)
    fichier = models.FileField(upload_to='sinistres/docs/')
    type_document = models.CharField(
        max_length=30,
        choices=[
            ('constat', 'Constat amiable'), ('photo', 'Photo'),
            ('facture', 'Facture réparation'), ('rapport', "Rapport d'expertise"),
            ('correspondance', 'Correspondance assureur'), ('autre', 'Autre')
        ],
        default='autre'
    )

    class Meta:
        verbose_name = "Pièce jointe sinistre"

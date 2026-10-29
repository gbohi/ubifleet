"""UbiFleet — Demandes & Workflow Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class TypeDemande(models.Model):
    """Référentiel des types de demandes, avec leur workflow de validation."""

    class Code(models.TextChoices):
        VEHICULE  = 'vehicule',  'Demande de véhicule / mission'
        ENTRETIEN = 'entretien', 'Demande d\'entretien / réparation'
        CARBURANT = 'carburant', 'Demande de carburant'
        ACHAT     = 'achat',     'Demande d\'achat de matériel'
        AUTRE     = 'autre',     'Autre demande'

    code             = models.CharField(
        max_length=50,
        help_text="Code du formulaire : achat, vehicule, entretien, carburant, autre (plusieurs types peuvent partager le même code)"
    )
    nom              = models.CharField(max_length=100)
    description      = models.TextField(blank=True)
    nb_niveaux       = models.PositiveSmallIntegerField(
        default=2, help_text="Nombre de niveaux de validation (1 à 4)"
    )
    actif            = models.BooleanField(default=True)
    delai_reponse_jours = models.PositiveSmallIntegerField(
        default=3, help_text="Délai de réponse attendu par niveau (jours)"
    )

    class Meta:
        verbose_name        = "Type de demande"
        verbose_name_plural = "Types de demande"
        ordering            = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.nb_niveaux} niveau(x))"


class NiveauValidation(models.Model):
    """Définit qui valide à chaque niveau pour un type de demande."""

    type_demande = models.ForeignKey(TypeDemande, on_delete=models.CASCADE,
                                      related_name='niveaux')
    niveau       = models.PositiveSmallIntegerField(help_text="1 = premier validateur")
    libelle      = models.CharField(max_length=100, help_text="Ex: 'Chef de service'")
    role_min     = models.ForeignKey(
        'accounts.Role', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='niveaux_validation',
        help_text="Rôle minimum requis pour valider à ce niveau"
    )

    class Meta:
        verbose_name        = "Niveau de validation"
        verbose_name_plural = "Niveaux de validation"
        unique_together     = ['type_demande', 'niveau']
        ordering            = ['type_demande', 'niveau']

    def __str__(self):
        return f"{self.type_demande.nom} — Niveau {self.niveau} ({self.libelle})"


class Demande(UbiFleetBaseModel):
    """Une demande soumise par un utilisateur."""

    class Statut(models.TextChoices):
        BROUILLON      = 'brouillon',      'Brouillon'
        SOUMISE        = 'soumise',        'Soumise'
        EN_VALIDATION  = 'en_validation',  'En cours de validation'
        APPROUVEE      = 'approuvee',      'Approuvée'
        REJETEE        = 'rejetee',        'Rejetée'
        ANNULEE        = 'annulee',        'Annulée'
        CLOTUREE       = 'cloturee',       'Clôturée'

    class Priorite(models.TextChoices):
        BASSE   = 'basse',   'Basse'
        NORMALE = 'normale', 'Normale'
        HAUTE   = 'haute',   'Haute'
        URGENTE = 'urgente', 'Urgente'

    # Identification
    numero        = models.CharField(max_length=20, unique=True, editable=False)
    type_demande  = models.ForeignKey(TypeDemande, on_delete=models.PROTECT,
                                       related_name='demandes')
    demandeur     = models.ForeignKey('accounts.User', on_delete=models.PROTECT,
                                       related_name='demandes_soumises')
    agence        = models.ForeignKey('accounts.Agence', on_delete=models.PROTECT,
                                       related_name='demandes', null=True, blank=True)

    # Workflow
    statut        = models.CharField(max_length=20, choices=Statut.choices,
                                      default=Statut.BROUILLON)
    niveau_actuel = models.PositiveSmallIntegerField(default=1)
    priorite      = models.CharField(max_length=10, choices=Priorite.choices,
                                      default=Priorite.NORMALE)

    # Contenu
    titre         = models.CharField(max_length=200)
    description   = models.TextField()
    date_souhaitee= models.DateField(null=True, blank=True,
                                      verbose_name="Date souhaitée")
    date_traitement = models.DateTimeField(null=True, blank=True,
                                            verbose_name="Date de traitement final")

    # Champs spécifiques selon le type
    vehicule      = models.ForeignKey('vehicules.Vehicule', null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='demandes',
                                       help_text="Pour les demandes de véhicule/entretien")
    chauffeur     = models.ForeignKey('chauffeurs.Chauffeur', null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='demandes')
    materiel      = models.CharField(max_length=300, blank=True,
                                      verbose_name="Matériel / fourniture demandé(e)")
    quantite      = models.DecimalField(max_digits=10, decimal_places=2,
                                         null=True, blank=True)
    unite         = models.CharField(max_length=30, blank=True,
                                      help_text="Ex: litres, unités, kg")
    fournisseur_suggere = models.CharField(max_length=200, blank=True)
    montant_estime      = models.DecimalField(max_digits=12, decimal_places=2,
                                               null=True, blank=True)
    fichier_joint       = models.FileField(upload_to='demandes/pj/', null=True, blank=True)
    notes_internes      = models.TextField(blank=True,
                                            verbose_name="Notes internes (non visibles par le demandeur)")

    class Meta:
        verbose_name        = "Demande"
        verbose_name_plural = "Demandes"
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.numero} — {self.titre}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone
        annee = timezone.now().year
        prefix = f"DEM-{annee}-"
        last = Demande.objects.filter(numero__startswith=prefix).count()
        return f"{prefix}{str(last + 1).zfill(4)}"

    def peut_etre_soumise(self):
        return self.statut == self.Statut.BROUILLON

    def peut_etre_annulee(self):
        return self.statut in [self.Statut.BROUILLON, self.Statut.SOUMISE,
                                self.Statut.EN_VALIDATION]


class ValidationDemande(UbiFleetBaseModel):
    """Historique des décisions de validation pour chaque demande."""

    class Decision(models.TextChoices):
        APPROUVE = 'approuve', 'Approuvé'
        REJETE   = 'rejete',   'Rejeté'
        EN_ATTENTE = 'en_attente', 'En attente'

    demande    = models.ForeignKey(Demande, on_delete=models.CASCADE,
                                    related_name='validations')
    niveau     = models.PositiveSmallIntegerField()
    validateur = models.ForeignKey('accounts.User', null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='validations_effectuees')
    decision   = models.CharField(max_length=15, choices=Decision.choices,
                                   default=Decision.EN_ATTENTE)
    commentaire= models.TextField(blank=True)
    date_decision = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Validation de demande"
        verbose_name_plural = "Validations de demande"
        ordering            = ['demande', 'niveau']
        unique_together     = ['demande', 'niveau']

    def __str__(self):
        return f"{self.demande.numero} — Niveau {self.niveau} — {self.get_decision_display()}"


class LigneDemandeAchat(models.Model):
    """Ligne de matériel pour une demande d'achat (code='achat')."""

    demande         = models.ForeignKey(
        Demande, on_delete=models.CASCADE, related_name='lignes_achat'
    )
    designation     = models.CharField(max_length=300, verbose_name="Désignation")
    quantite        = models.DecimalField(max_digits=10, decimal_places=2)
    unite           = models.CharField(max_length=30, blank=True,
                                        help_text="Ex: unités, kg, litres")
    prix_unitaire   = models.DecimalField(max_digits=12, decimal_places=2,
                                           null=True, blank=True,
                                           verbose_name="Prix unitaire estimé (FCFA)")
    fournisseur     = models.CharField(max_length=200, blank=True)
    notes           = models.CharField(max_length=300, blank=True)
    ordre           = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = "Ligne de demande d'achat"
        verbose_name_plural = "Lignes de demande d'achat"
        ordering            = ['ordre', 'id']

    def __str__(self):
        return f"{self.designation} × {self.quantite}"

    @property
    def montant_ligne(self):
        if self.prix_unitaire:
            return self.quantite * self.prix_unitaire
        return None

"""UbiFleet — Contrôle Véhicule Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class ElementControle(models.Model):
    """Référentiel des points à contrôler — configurable depuis les Paramètres."""

    class Categorie(models.TextChoices):
        MOTEUR      = 'moteur',      'Moteur'
        SECURITE    = 'securite',    'Sécurité'
        CARROSSERIE = 'carrosserie', 'Carrosserie'
        ECLAIRAGE   = 'eclairage',   'Éclairage'
        PNEUMATIQUES= 'pneumatiques','Pneumatiques'
        INTERIEUR   = 'interieur',   'Intérieur'
        ADMINISTRATIF='administratif','Administratif'
        AUTRE       = 'autre',       'Autre'

    nom        = models.CharField(max_length=100, verbose_name="Nom du point")
    categorie  = models.CharField(max_length=20, choices=Categorie.choices,
                                   default=Categorie.AUTRE)
    description= models.TextField(blank=True)
    ordre      = models.PositiveSmallIntegerField(default=0)
    actif      = models.BooleanField(default=True)
    obligatoire= models.BooleanField(default=False,
                    help_text="Point obligatoire — la fiche ne peut être validée si non conforme")

    class Meta:
        verbose_name        = "Élément de contrôle"
        verbose_name_plural = "Éléments de contrôle"
        ordering            = ['categorie', 'ordre', 'nom']

    def __str__(self):
        return f"{self.get_categorie_display()} — {self.nom}"


class FicheControle(UbiFleetBaseModel):
    """Fiche de contrôle complète d'un véhicule."""

    class TypeControle(models.TextChoices):
        DEPART          = 'depart',          'Contrôle départ'
        RETOUR          = 'retour',          'Contrôle retour'
        PERIODIQUE      = 'periodique',      'Contrôle périodique'
        APRES_SINISTRE  = 'apres_sinistre',  'Après sinistre'
        APRES_REPARATION= 'apres_reparation','Après réparation'

    class StatutGlobal(models.TextChoices):
        CONFORME     = 'conforme',     'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'
        PARTIEL      = 'partiel',      'Partiellement conforme'
        EN_COURS     = 'en_cours',     'En cours'

    vehicule        = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.CASCADE,
        related_name='fiches_controle'
    )
    chauffeur       = models.ForeignKey(
        'chauffeurs.Chauffeur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fiches_controle'
    )
    agence          = models.ForeignKey(
        'accounts.Agence', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fiches_controle'
    )
    type_controle   = models.CharField(max_length=20, choices=TypeControle.choices,
                                        default=TypeControle.PERIODIQUE)
    statut_global   = models.CharField(max_length=20, choices=StatutGlobal.choices,
                                        default=StatutGlobal.EN_COURS)
    date_heure      = models.DateTimeField(verbose_name="Date et heure du contrôle")
    kilometrage     = models.PositiveIntegerField(verbose_name="Kilométrage au compteur")
    notes_generales = models.TextField(blank=True, verbose_name="Notes générales")
    signature_controleur = models.ImageField(
        upload_to='controle/signatures/', null=True, blank=True
    )

    class Meta:
        verbose_name        = "Fiche de contrôle"
        verbose_name_plural = "Fiches de contrôle"
        ordering            = ['-date_heure']

    def __str__(self):
        return (f"Contrôle {self.get_type_controle_display()} — "
                f"{self.vehicule.immatriculation} — "
                f"{self.date_heure.strftime('%d/%m/%Y %H:%M')}")

    def calculer_statut_global(self):
        """Recalcule le statut global selon les points non conformes."""
        details = self.points.all()
        if not details.exists():
            return self.StatutGlobal.EN_COURS
        nc = details.filter(statut='non_conforme')
        if not nc.exists():
            return self.StatutGlobal.CONFORME
        if nc.filter(gravite='bloquant').exists():
            return self.StatutGlobal.NON_CONFORME
        return self.StatutGlobal.PARTIEL

    def save(self, *args, **kwargs):
        if self.pk and self.statut_global != self.StatutGlobal.EN_COURS:
            self.statut_global = self.calculer_statut_global()
        super().save(*args, **kwargs)


class PointControleDetail(models.Model):
    """Résultat d'un point de contrôle dans une fiche."""

    class Statut(models.TextChoices):
        CONFORME     = 'conforme',     'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'
        NA           = 'na',           'Non applicable'

    class Gravite(models.TextChoices):
        MINEUR   = 'mineur',   'Mineur'
        MAJEUR   = 'majeur',   'Majeur'
        BLOQUANT = 'bloquant', 'Bloquant'

    fiche   = models.ForeignKey(FicheControle, on_delete=models.CASCADE,
                                 related_name='points')
    element = models.ForeignKey(ElementControle, on_delete=models.PROTECT,
                                 related_name='details')
    statut  = models.CharField(max_length=20, choices=Statut.choices,
                                default=Statut.CONFORME)
    gravite = models.CharField(max_length=10, choices=Gravite.choices,
                                null=True, blank=True,
                                help_text="Renseigné seulement si non conforme")
    remarque    = models.TextField(blank=True)
    photo_point = models.ImageField(upload_to='controle/points/', null=True, blank=True)

    class Meta:
        verbose_name        = "Point de contrôle"
        verbose_name_plural = "Points de contrôle"
        unique_together     = ['fiche', 'element']
        ordering            = ['element__categorie', 'element__ordre']

    def __str__(self):
        return f"{self.element.nom} — {self.get_statut_display()}"

    def save(self, *args, **kwargs):
        # Nettoyer gravite si conforme
        if self.statut != self.Statut.NON_CONFORME:
            self.gravite = None
        super().save(*args, **kwargs)


class PhotoControle(models.Model):
    """Photos générales attachées à une fiche de contrôle."""

    class TypePhoto(models.TextChoices):
        AVANT     = 'avant',     'Avant'
        ARRIERE   = 'arriere',   'Arrière'
        GAUCHE    = 'gauche',    'Côté gauche'
        DROITE    = 'droite',    'Côté droit'
        INTERIEUR = 'interieur', 'Intérieur'
        MOTEUR    = 'moteur',    'Compartiment moteur'
        AUTRE     = 'autre',     'Autre'

    fiche      = models.ForeignKey(FicheControle, on_delete=models.CASCADE,
                                    related_name='photos')
    image      = models.ImageField(upload_to='controle/photos/')
    type_photo = models.CharField(max_length=15, choices=TypePhoto.choices,
                                   default=TypePhoto.AUTRE)
    legende    = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Photo de contrôle"
        verbose_name_plural = "Photos de contrôle"
        ordering            = ['type_photo']

    def __str__(self):
        return f"{self.fiche} — {self.get_type_photo_display()}"

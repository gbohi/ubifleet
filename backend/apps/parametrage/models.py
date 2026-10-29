"""UbiFleet — Paramétrage système"""
from django.db import models


class Parametre(models.Model):
    """Paramètres configurables de l'application."""

    class Categorie(models.TextChoices):
        ALERTES   = 'alertes',   'Alertes'
        CARBURANT = 'carburant', 'Carburant'
        GENERAL   = 'general',   'Général'

    cle = models.CharField(max_length=100, unique=True, verbose_name="Clé")
    valeur = models.CharField(max_length=500, verbose_name="Valeur")
    description = models.CharField(max_length=300, blank=True)
    categorie = models.CharField(
        max_length=20, choices=Categorie.choices,
        default=Categorie.GENERAL
    )
    type_valeur = models.CharField(
        max_length=10,
        choices=[('int','Entier'),('float','Décimal'),('str','Texte'),('bool','Booléen')],
        default='str'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre"
        verbose_name_plural = "Paramètres"
        ordering = ['categorie', 'cle']

    def __str__(self):
        return f"{self.cle} = {self.valeur}"

    def valeur_typee(self):
        """Retourne la valeur dans son type natif."""
        if self.type_valeur == 'int':
            return int(self.valeur)
        if self.type_valeur == 'float':
            return float(self.valeur)
        if self.type_valeur == 'bool':
            return self.valeur.lower() in ('true', '1', 'oui')
        return self.valeur

    @classmethod
    def get(cls, cle: str, defaut=None):
        """Récupère une valeur de paramètre avec valeur par défaut."""
        try:
            p = cls.objects.get(cle=cle)
            return p.valeur_typee()
        except cls.DoesNotExist:
            return defaut


class Tournee(models.Model):
    """Tournées de véhicules — référentiel configurable."""
    code          = models.CharField(max_length=20, unique=True, verbose_name="Code")
    libelle       = models.CharField(max_length=100, verbose_name="Libellé")
    agence        = models.ForeignKey(
        'accounts.Agence', on_delete=models.PROTECT,
        related_name='tournees', verbose_name="Agence"
    )
    dotation      = models.PositiveIntegerField(
        default=0, verbose_name="Dotation (L)",
        help_text="Quantité de carburant allouée par tournée (litres)"
    )
    km_theorique  = models.PositiveIntegerField(
        default=0, verbose_name="Km théorique",
        help_text="Kilométrage théorique de la tournée"
    )
    actif         = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Tournée"
        verbose_name_plural = "Tournées"
        ordering            = ['code']

    def __str__(self):
        return f"{self.code} — {self.libelle}"


class AffectationUsage(models.Model):
    """Types d'affectation / usage des véhicules."""
    code     = models.CharField(max_length=20, unique=True)
    libelle  = models.CharField(max_length=100)
    actif    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Affectation / Usage"
        verbose_name_plural = "Affectations / Usages"
        ordering            = ['code']

    def __str__(self):
        return f"{self.code} — {self.libelle}"


class StatutVehicule(models.Model):
    """Statuts configurables des véhicules."""
    code     = models.CharField(max_length=30, unique=True)
    libelle  = models.CharField(max_length=100)
    couleur  = models.CharField(
        max_length=20, default='gray',
        help_text="Couleur d'affichage : green, red, orange, blue, gray"
    )
    actif    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Statut véhicule"
        verbose_name_plural = "Statuts véhicule"
        ordering            = ['libelle']

    def __str__(self):
        return f"{self.libelle}"


class MarqueVehicule(models.Model):
    """Marques de véhicules paramétrables."""
    libelle  = models.CharField(max_length=100, unique=True)
    actif    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Marque véhicule"
        verbose_name_plural = "Marques véhicule"
        ordering            = ['libelle']

    def __str__(self):
        return self.libelle


class ModeleVehicule(models.Model):
    """Modèles de véhicules paramétrables, rattachés à une marque."""
    marque   = models.ForeignKey(
        MarqueVehicule, on_delete=models.CASCADE, related_name='modeles'
    )
    libelle  = models.CharField(max_length=120)
    actif    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Modèle véhicule"
        verbose_name_plural = "Modèles véhicule"
        ordering            = ['marque__libelle', 'libelle']
        unique_together     = [('marque', 'libelle')]

    def __str__(self):
        return f"{self.marque.libelle} {self.libelle}"

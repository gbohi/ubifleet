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


class TypeMouvement(models.Model):
    """Types de mouvement des relevés kilométriques et des prises de carburant
    (sortie, retour, tournée, course...). Chaque type indique à quelles
    saisies il s'applique. Le type `tournee` est réservé : il demande la
    tournée (référentiel Tournée), sert aux deux saisies et ne peut être ni
    supprimé ni recodé."""
    CODE_TOURNEE = 'tournee'

    class Couleur(models.TextChoices):
        VERT   = 'green',  'Vert'
        ORANGE = 'orange', 'Orange'
        BLEU   = 'blue',   'Bleu'
        ROUGE  = 'red',    'Rouge'
        GRIS   = 'gray',   'Gris'

    code         = models.SlugField(max_length=20, unique=True,
                                    help_text="Identifiant technique, enregistré sur les relevés.")
    libelle      = models.CharField(max_length=100)
    couleur      = models.CharField(max_length=10, choices=Couleur.choices, default=Couleur.GRIS)
    ordre        = models.PositiveSmallIntegerField(default=0)
    actif        = models.BooleanField(default=True)
    pour_releves = models.BooleanField(default=True, verbose_name="Relevés kilométriques")
    pour_prises  = models.BooleanField(default=False, verbose_name="Prises de carburant")
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Type de mouvement"
        verbose_name_plural = "Types de mouvement"
        ordering            = ['ordre', 'libelle']

    def __str__(self):
        return self.libelle


class ChangementDotation(models.Model):
    """Historique de la dotation d'une tournée.

    Une modification passe par une demande validée selon le circuit « dotation »
    (Paramètres › Circuits de validation) ; la tournée n'est mise à jour qu'à
    l'approbation finale.
    """

    class Statut(models.TextChoices):
        INITIALE   = 'initiale',   'Dotation initiale'
        EN_ATTENTE = 'en_attente', 'En attente de validation'
        APPROUVEE  = 'approuvee',  'Approuvée et appliquée'
        REJETEE    = 'rejetee',    'Rejetée'
        ANNULEE    = 'annulee',    'Annulée'

    tournee           = models.ForeignKey(Tournee, on_delete=models.CASCADE, related_name='changements_dotation')
    ancienne_dotation = models.PositiveIntegerField(null=True, blank=True)
    nouvelle_dotation = models.PositiveIntegerField()
    motif             = models.TextField(blank=True)
    statut            = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    demande           = models.OneToOneField(
        'demandes.Demande', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='changement_dotation'
    )
    demandeur         = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='changements_dotation_demandes'
    )
    decide_par        = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='changements_dotation_decides'
    )
    date_decision     = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Changement de dotation"
        verbose_name_plural = "Changements de dotation"
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.tournee.code} : {self.ancienne_dotation} → {self.nouvelle_dotation} L ({self.statut})"


class CorrectionSaisie(models.Model):
    """Journal des modifications et suppressions de pleins et de relevés
    kilométriques : qui, quand, valeurs avant / après, motif."""

    class Action(models.TextChoices):
        MODIFICATION = 'modification', 'Modification'
        SUPPRESSION  = 'suppression',  'Suppression'

    domaine  = models.CharField(max_length=20, verbose_name="Domaine")   # carburant | releves
    objet_id = models.UUIDField(verbose_name="Saisie concernée")
    libelle  = models.CharField(max_length=200, verbose_name="Saisie")
    vehicule = models.ForeignKey('vehicules.Vehicule', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='corrections_saisie')
    action   = models.CharField(max_length=15, choices=Action.choices)
    auteur   = models.ForeignKey('accounts.User', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='+')
    date     = models.DateTimeField(auto_now_add=True)
    hors_delai = models.BooleanField(default=False)
    motif    = models.TextField(blank=True)
    # [{champ, libelle, avant, apres}] — valeurs lisibles
    changements = models.JSONField(default=list)

    class Meta:
        verbose_name        = "Correction de saisie"
        verbose_name_plural = "Corrections de saisie"
        ordering            = ['-date']
        indexes             = [models.Index(fields=['domaine', 'objet_id'])]

    def __str__(self):
        return f"{self.get_action_display()} — {self.libelle}"

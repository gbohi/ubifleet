"""UbiFleet — Véhicules Models"""

import uuid
from django.db import models
from django.db.models import F
from apps.core.models import UbiFleetBaseModel

class Vehicule(UbiFleetBaseModel):
    """Véhicule du parc Ubipharm."""

    class Statut(models.TextChoices):
        EN_SERVICE = 'en_service', 'En service'
        EN_REVISION = 'en_revision', 'En révision'
        IMMOBILISE = 'immobilise', 'Immobilisé'
        VENDU = 'vendu', 'Vendu / Réformé'
        EN_PANNE = 'en_panne', 'En panne'

    class TypeCarburant(models.TextChoices):
        DIESEL = 'diesel', 'Diesel'
        ESSENCE = 'essence', 'Essence'
        HYBRIDE = 'hybride', 'Hybride'
        ELECTRIQUE = 'electrique', 'Électrique'
        GPL = 'gpl', 'GPL'

    class TypeVehicule(models.TextChoices):
        BERLINE = 'berline', 'Berline'
        SUV = 'suv', 'SUV / 4×4'
        MINIBUS = 'minibus', 'Minibus'
        CAMIONNETTE = 'camionnette', 'Camionnette / Fourgonnette'
        PICKUP = 'pickup', 'Pick-up'
        CAMION = 'camion', 'Camion'
        MOTO = 'moto', 'Moto'

    # Identification
    immatriculation = models.CharField(
        max_length=20, unique=True,
        verbose_name="Immatriculation"
    )
    numero_chassis = models.CharField(
        max_length=50, blank=True, unique=True, null=True,
        verbose_name="N° de châssis (VIN)"
    )
    immatriculation_provisoire = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name="Immatriculation provisoire (ancienne)"
    )
    est_immatriculation_provisoire = models.BooleanField(
        default=False,
        verbose_name="Immatriculation encore provisoire"
    )
    date_immatriculation_definitive = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'immatriculation définitive"
    )
    marque = models.ForeignKey(
        'parametrage.MarqueVehicule', on_delete=models.PROTECT,
        null=True, blank=True, related_name='vehicules',
        verbose_name="Marque"
    )
    modele = models.ForeignKey(
        'parametrage.ModeleVehicule', on_delete=models.PROTECT,
        null=True, blank=True, related_name='vehicules',
        verbose_name="Modèle"
    )
    annee = models.PositiveSmallIntegerField(verbose_name="Année")
    couleur = models.CharField(max_length=50, blank=True)

    # Classification
    type_vehicule = models.CharField(
        max_length=20, choices=TypeVehicule.choices,
        default=TypeVehicule.BERLINE
    )
    type_carburant = models.CharField(
        max_length=15, choices=TypeCarburant.choices,
        default=TypeCarburant.DIESEL
    )
    nombre_places = models.PositiveSmallIntegerField(default=5)

    # Affectation
    agence = models.ForeignKey(
        'accounts.Agence',
        on_delete=models.PROTECT,
        related_name='vehicules',
        verbose_name="Agence"
    )
    affectation = models.ForeignKey(
        'parametrage.AffectationUsage',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicules',
        verbose_name="Affectation / Usage"
    )
    chauffeur_attitré = models.ForeignKey(
        'chauffeurs.Chauffeur', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='vehicule_attitré',
        verbose_name="Chauffeur attitré"
    )

    # État
    statut = models.ForeignKey(
        'parametrage.StatutVehicule',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicules',
        verbose_name='Statut'
    )
    kilometrage_actuel = models.PositiveIntegerField(
        default=0, verbose_name="Kilométrage actuel"
    )
    # Plancher du compteur : kilométrage à l'entrée dans le parc (cf. vehicules.kilometrage)
    kilometrage_initial = models.PositiveIntegerField(
        default=0, verbose_name="Kilométrage à l'entrée dans le parc"
    )
    conso_theorique_origine = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Consommation théorique de référence (L/100km)",
        help_text="Sert à estimer les litres attendus des prises hors tournée ; "
                  "à défaut, la moyenne observée sur les prises du véhicule est utilisée.",
    )
    kilometrage_revision = models.PositiveIntegerField(
        default=0, verbose_name="Km prochain entretien"
    )

    # Dates
    date_mise_en_service = models.DateField(
        null=True, blank=True,
        verbose_name="Date de mise en service"
    )
    date_acquisition = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'acquisition"
    )

    # Financier
    valeur_acquisition = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        verbose_name="Valeur d'acquisition (FCFA)"
    )
    dotation_carburant_mensuelle = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=0,
        verbose_name="Dotation carburant mensuelle (L)"
    )

    # Documents
    carte_grise = models.FileField(
        upload_to='vehicules/docs/', null=True, blank=True,
        verbose_name="Carte grise"
    )
    photo = models.ImageField(
        upload_to='vehicules/photos/', null=True, blank=True,
        verbose_name="Photo du véhicule"
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Véhicule"
        verbose_name_plural = "Véhicules"
        ordering = ['immatriculation']

    @property
    def marque_str(self):
        return self.marque.libelle if self.marque else ''

    @property
    def modele_str(self):
        return self.modele.libelle if self.modele else ''

    def __str__(self):
        return f"{self.immatriculation} — {self.marque_str} {self.modele_str} ({self.annee})"

    @property
    def designation(self):
        return f"{self.marque_str} {self.modele_str} {self.annee}".strip()

    @property
    def revision_due(self):
        if self.kilometrage_revision > 0:
            return self.kilometrage_actuel >= self.kilometrage_revision
        return False

    def consommation_moyenne(self):
        """
        Consommation moyenne L/100km sur l'historique des pleins.
        Trie par date + heure (pas par kilométrage) pour rester cohérent
        avec l'ordre chronologique réel des évènements.
        """
        from apps.carburant.models import PleinsCarburant
        pleins = list(
            PleinsCarburant.objects.filter(vehicule=self)
            .order_by('date_plein', 'heure_plein')
        )
        if len(pleins) < 2:
            return None

        premier = pleins[0]
        dernier = pleins[-1]
        km_total = dernier.kilometrage_releve - premier.kilometrage_releve
        if km_total <= 0:
            return None

        # Volume total consommé sur la période, hors premier plein
        # (le premier plein sert de référence kilométrique de départ,
        # son volume n'a pas permis de parcourir les km comptés ici)
        total_litres = sum(p.volume_litres for p in pleins[1:])
        return round(float(total_litres) / km_total * 100, 2)


class TypeDocumentVehicule(models.Model):
    """Types de documents véhicule — gérables depuis l'interface."""
    code    = models.CharField(max_length=50, unique=True, verbose_name="Code")
    libelle = models.CharField(max_length=100, verbose_name="Libellé")
    actif   = models.BooleanField(default=True)
    ordre   = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")

    # Codes réservés pour le calcul État du Parc
    CODE_ASSURANCE       = 'assurance'
    CODE_CT              = 'ct'
    CODE_CARTE_TRANSPORT = 'carte_transport'
    CODE_VIGNETTE        = 'vignette'

    class Meta:
        verbose_name          = "Type de document véhicule"
        verbose_name_plural   = "Types de documents véhicule"
        ordering              = ['ordre', 'libelle']

    def __str__(self):
        return self.libelle


class DocumentVehicule(UbiFleetBaseModel):
    """Documents associés à un véhicule (assurance, CT, etc.)."""

    vehicule = models.ForeignKey(
        Vehicule, on_delete=models.CASCADE,
        related_name='documents'
    )
    type_document = models.ForeignKey(
        TypeDocumentVehicule,
        on_delete=models.PROTECT,
        related_name='documents',
        verbose_name="Type de document"
    )
    numero          = models.CharField(max_length=100, blank=True)
    date_emission   = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)
    fichier         = models.FileField(upload_to='vehicules/documents/')
    notes           = models.TextField(blank=True)

    class Meta:
        verbose_name = "Document véhicule"
        verbose_name_plural = "Documents véhicules"

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.type_document.libelle}"

    @property
    def est_expire(self):
        if self.date_expiration:
            from django.utils import timezone
            return self.date_expiration < timezone.now().date()
        return False


class ReleveKilometrage(models.Model):
    """Historique des relevés de kilométrage."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    vehicule   = models.ForeignKey(
        Vehicule, on_delete=models.CASCADE,
        related_name='releves_kilometrage'
    )
    kilometrage = models.PositiveIntegerField(verbose_name='Kilométrage relevé (km)')
    date_releve = models.DateField(verbose_name='Date du relevé')
    # Distingue les relevés d'une même journée ; vide pour les relevés antérieurs
    heure_releve = models.TimeField(null=True, blank=True, verbose_name='Heure du relevé')
    # Code d'un type de mouvement paramétrable (Paramètres › Types de mouvement)
    type_mouvement = models.CharField(max_length=20, default='releve')
    # Obligatoire pour le type de mouvement « tournée », vide pour les autres
    tournee  = models.ForeignKey(
        'parametrage.Tournee', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='releves_kilometrage', verbose_name='Tournée'
    )
    notes    = models.TextField(blank=True)
    chauffeur = models.ForeignKey(
        'chauffeurs.Chauffeur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='releves_kilometrage',
        verbose_name='Chauffeur'
    )
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='releves_saisis'
    )
    photo_tableau_bord = models.ImageField(
        upload_to='vehicules/releves/', null=True, blank=True,
        verbose_name='Photo tableau de bord'
    )
    # Saisie / correction hors de la fenêtre de saisie (cf. parametrage.fenetre_saisie)
    saisie_hors_delai = models.BooleanField(default=False, verbose_name="Saisi hors délai")
    hors_delai_par = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name="Hors délai : par"
    )
    hors_delai_le = models.DateTimeField(null=True, blank=True, verbose_name="Hors délai : le")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name         = 'Relevé kilométrage'
        verbose_name_plural  = 'Relevés kilométrage'
        ordering             = ['-date_releve', F('heure_releve').desc(nulls_last=True), '-created_at']

    def __str__(self):
        return (f"{self.vehicule.immatriculation} — "
                f"{self.kilometrage} km — {self.date_releve}")


class HistoriqueImmatriculation(models.Model):
    """Historique des changements d'immatriculation d'un véhicule."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicule = models.ForeignKey(
        Vehicule, on_delete=models.CASCADE,
        related_name='historique_immatriculations'
    )
    ancienne_immatriculation = models.CharField(max_length=20)
    nouvelle_immatriculation = models.CharField(max_length=20)
    date_changement = models.DateField()
    motif = models.CharField(
        max_length=200, blank=True,
        help_text='ex: Passage de provisoire à définitive, correction, etc.'
    )
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name         = "Historique immatriculation"
        verbose_name_plural  = "Historiques immatriculations"
        ordering             = ['-date_changement']

    def __str__(self):
        return (f"{self.ancienne_immatriculation} → "
                f"{self.nouvelle_immatriculation} ({self.date_changement})")


class AffectationVehicule(models.Model):
    """Affectation d'un véhicule à un chauffeur (Many-to-Many avec attributs)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    vehicule = models.ForeignKey(
        Vehicule, on_delete=models.CASCADE,
        related_name='affectations'
    )
    chauffeur = models.ForeignKey(
        'chauffeurs.Chauffeur', on_delete=models.CASCADE,
        related_name='affectations'
    )
    date_debut  = models.DateField(verbose_name='Date de début')
    date_fin    = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    notes       = models.TextField(blank=True)
    created_by  = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='affectations_creees'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name         = 'Affectation véhicule'
        verbose_name_plural  = 'Affectations véhicules'
        ordering             = ['-date_debut']

    @property
    def est_active(self):
        from datetime import date
        return self.date_fin is None or self.date_fin >= date.today()

    def __str__(self):
        return (f"{self.vehicule.immatriculation} → "
                f"{self.chauffeur.nom} {self.chauffeur.prenom} "
                f"(dès {self.date_debut})")


class HistoriqueStatutVehicule(models.Model):
    """Historique des changements de statut d'un véhicule."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicule = models.ForeignKey(
        Vehicule, on_delete=models.CASCADE,
        related_name='historique_statuts'
    )
    ancien_statut = models.ForeignKey(
        'parametrage.StatutVehicule',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='historiques_ancien'
    )
    nouveau_statut = models.ForeignKey(
        'parametrage.StatutVehicule',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='historiques_nouveau'
    )
    motif      = models.CharField(max_length=300, blank=True)
    date_changement = models.DateField()
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Historique statut véhicule"
        verbose_name_plural = "Historiques statuts véhicule"
        ordering            = ['-date_changement', '-created_at']

    def __str__(self):
        return (f"{self.vehicule.immatriculation} — "
                f"{self.ancien_statut} → {self.nouveau_statut} "
                f"({self.date_changement})")

"""UbiFleet — Carburant Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class Station(UbiFleetBaseModel):
    """Station-service / fournisseur carburant."""
    nom = models.CharField(max_length=100)
    ville = models.CharField(max_length=100, blank=True)
    adresse = models.TextField(blank=True)
    agence = models.ForeignKey(
        'accounts.Agence', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stations'
    )
    est_partenaire = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Station-service"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class DotationCarburant(UbiFleetBaseModel):
    """Dotation mensuelle d'un véhicule."""
    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.CASCADE,
        related_name='dotations'
    )
    mois = models.PositiveSmallIntegerField(verbose_name="Mois (1-12)")
    annee = models.PositiveSmallIntegerField(verbose_name="Année")
    volume_alloue = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name="Volume alloué (L)"
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Dotation carburant"
        unique_together = ['vehicule', 'mois', 'annee']
        ordering = ['-annee', '-mois']

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.mois}/{self.annee} — {self.volume_alloue}L"

    @property
    def volume_consomme(self):
        return self.vehicule.pleins.filter(
            date_plein__month=self.mois,
            date_plein__year=self.annee
        ).aggregate(
            total=models.Sum('volume_litres')
        )['total'] or 0

    @property
    def taux_utilisation(self):
        if self.volume_alloue <= 0:
            return 0
        return round((float(self.volume_consomme) / float(self.volume_alloue)) * 100, 1)


class TourneeEffectuee(UbiFleetBaseModel):
    """Réalisation d'une tournée par un véhicule : ouverte par la première
    prise de carburant de type « tournée », elle regroupe les prises jusqu'à
    sa clôture (KM retour saisi). Dotation et km théorique sont figés à
    l'ouverture, pour que les tournées passées ne changent pas si la
    dotation de la tournée est modifiée."""

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CLOTUREE = 'cloturee', 'Clôturée'
        ANNULEE  = 'annulee',  'Annulée'

    numero    = models.CharField(max_length=40, unique=True)
    tournee   = models.ForeignKey('parametrage.Tournee', on_delete=models.PROTECT,
                                  related_name='realisations', verbose_name='Tournée')
    vehicule  = models.ForeignKey('vehicules.Vehicule', on_delete=models.CASCADE,
                                  related_name='tournees_effectuees')
    chauffeur = models.ForeignKey('chauffeurs.Chauffeur', null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name='tournees_effectuees')
    agence    = models.ForeignKey('accounts.Agence', on_delete=models.PROTECT,
                                  related_name='tournees_effectuees')
    statut    = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    # Début = première prise (recalculé si elle est corrigée ou supprimée)
    date_debut  = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    km_depart   = models.PositiveIntegerField()
    # Clôture
    date_fin    = models.DateField(null=True, blank=True)
    heure_fin   = models.TimeField(null=True, blank=True)
    km_retour   = models.PositiveIntegerField(null=True, blank=True)
    cloturee_par = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='+')
    cloturee_le  = models.DateTimeField(null=True, blank=True)
    # Relevé kilométrique de retour créé à la clôture (KM retour > dernière prise)
    releve_retour = models.ForeignKey('vehicules.ReleveKilometrage', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='+')
    # Théorique figé à l'ouverture
    dotation_theorique = models.PositiveIntegerField(default=0, verbose_name='Dotation théorique (L)')
    km_theorique       = models.PositiveIntegerField(default=0, verbose_name='Km théorique')
    commentaire  = models.TextField(blank=True)
    motif_annulation = models.TextField(blank=True)
    # Reprise des prises saisies avant les tournées effectuées : à vérifier
    a_verifier   = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Tournée effectuée'
        verbose_name_plural = 'Tournées effectuées'
        ordering = ['-date_debut', '-heure_debut']
        constraints = [
            models.UniqueConstraint(fields=['vehicule'], condition=models.Q(statut='en_cours'),
                                    name='une_tournee_en_cours_par_vehicule'),
        ]

    def __str__(self):
        return self.numero


class PleinsCarburant(UbiFleetBaseModel):
    """Prise de carburant (le modèle garde son nom historique « plein »)."""

    class StatutValidation(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        VALIDE = 'valide', 'Validé'
        ANOMALIE = 'anomalie', 'Anomalie détectée'
        REJETE = 'rejete', 'Rejeté'

    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.CASCADE,
        related_name='pleins'
    )
    chauffeur = models.ForeignKey(
        'chauffeurs.Chauffeur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pleins'
    )
    tournee = models.ForeignKey(
        'parametrage.Tournee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pleins',
        verbose_name='Tournée'
    )
    # Type de mouvement (Paramètres › Types de mouvement, saisie « prises ») ;
    # le type « tournee » rattache la prise à une tournée effectuée.
    type_mouvement = models.CharField(max_length=20, default='tournee', verbose_name='Type de mouvement')
    tournee_effectuee = models.ForeignKey(
        TourneeEffectuee, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='prises', verbose_name='Tournée effectuée'
    )
    station = models.ForeignKey(
        Station, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pleins'
    )
    date_plein = models.DateField(verbose_name="Date de la prise")
    heure_plein = models.TimeField(
        null=True, blank=True,
        verbose_name="Heure de la prise"
    )
    volume_litres = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name="Volume (L)"
    )
    prix_litre = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        verbose_name="Prix au litre (FCFA)"
    )
    montant_fcfa = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Montant total (FCFA)"
    )
    kilometrage_depart = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Kilométrage départ (km de la prise précédente)"
    )
    kilometrage_releve = models.PositiveIntegerField(
        verbose_name="Kilométrage relevé"
    )
    consommation_calculee = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        verbose_name="Consommation calculée (L/100km)"
    )
    bon_carburant = models.CharField(
        max_length=50, blank=True,
        verbose_name="N° bon de carburant"
    )
    photo_bon = models.ImageField(
        upload_to='carburant/bons/',
        null=True, blank=True,
        verbose_name="Photo du bon"
    )
    photo_tableau_bord = models.ImageField(
        upload_to='carburant/tableaux_bord/',
        null=True, blank=True,
        verbose_name="Photo tableau de bord"
    )
    # Plus de circuit de validation : une prise enregistrée est valide, sauf
    # consommation anormale détectée à l'enregistrement (statut « anomalie »).
    statut_validation = models.CharField(
        max_length=15, choices=StatutValidation.choices,
        default=StatutValidation.VALIDE
    )
    motif_anomalie = models.TextField(blank=True)
    # Saisie / correction hors de la fenêtre de saisie (cf. parametrage.fenetre_saisie)
    saisie_hors_delai = models.BooleanField(default=False, verbose_name="Saisi hors délai")
    hors_delai_par = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name="Hors délai : par"
    )
    hors_delai_le = models.DateTimeField(null=True, blank=True, verbose_name="Hors délai : le")
    valide_par = models.ForeignKey(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pleins_valides'
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.PROTECT,
        related_name='pleins'
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prise de carburant"
        verbose_name_plural = "Prises de carburant"
        ordering = ['-date_plein', '-created_at']

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.date_plein} — {self.volume_litres}L"

    def save(self, *args, **kwargs):
        # Prix non renseigné : prix en vigueur à la date du plein (historique daté)
        if not self.prix_litre and self.vehicule_id and self.date_plein:
            prix = PrixCarburant.en_vigueur(self.vehicule.type_carburant, self.date_plein)
            if prix:
                self.prix_litre = prix.prix

        # Consommation et anomalie (cf. anomalies.py) ; le km de départ est
        # celui de la prise précédente. Les prises suivantes sont recalculées
        # par recalculer_consommations après l'enregistrement.
        if self.kilometrage_releve and self.vehicule_id and self.date_plein:
            from .anomalies import evaluer, ordre_chronologique, statut_et_motif
            autres = PleinsCarburant.objects.filter(vehicule_id=self.vehicule_id).exclude(pk=self.pk)
            ev = evaluer(sorted([*autres, self], key=ordre_chronologique))[self.pk]
            if ev.depart is not None and not self.kilometrage_depart:
                self.kilometrage_depart = ev.depart
            self.consommation_calculee = ev.conso
            self.statut_validation, self.motif_anomalie = statut_et_motif(self, ev)

        # MAJ kilométrage véhicule
        if self.vehicule and self.kilometrage_releve > self.vehicule.kilometrage_actuel:
            self.vehicule.kilometrage_actuel = self.kilometrage_releve
            self.vehicule.save(update_fields=['kilometrage_actuel'])

        super().save(*args, **kwargs)
        # Dépense « Carburant » du budget (cf. depenses.py)
        from .depenses import synchroniser_depense
        synchroniser_depense(self)


class RapprochementCarburant(UbiFleetBaseModel):
    """Rapprochement mensuel avec les factures fournisseurs."""
    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.PROTECT,
        related_name='rapprochements'
    )
    station = models.ForeignKey(
        Station, on_delete=models.PROTECT,
        related_name='rapprochements'
    )
    mois = models.PositiveSmallIntegerField()
    annee = models.PositiveSmallIntegerField()
    montant_facture = models.DecimalField(max_digits=12, decimal_places=2)
    montant_saisi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ecart = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    statut = models.CharField(
        max_length=20,
        choices=[('en_cours','En cours'),('rapproche','Rapproché'),('ecart','Écart')],
        default='en_cours'
    )
    fichier_facture = models.FileField(upload_to='carburant/factures/', null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['agence', 'station', 'mois', 'annee']
        verbose_name = "Rapprochement carburant"

    def save(self, *args, **kwargs):
        self.ecart = self.montant_facture - self.montant_saisi
        if abs(float(self.ecart)) < 100:
            self.statut = 'rapproche'
        elif self.ecart != 0:
            self.statut = 'ecart'
        super().save(*args, **kwargs)


class PrixCarburant(models.Model):
    """Historique daté du prix du litre, par type de carburant.

    Le prix applicable à une date est celui de la dernière entrée dont la date
    d'effet est antérieure ou égale à cette date. Les entrées passées ne sont
    pas modifiables : un nouveau prix s'ajoute avec sa date d'effet.
    """
    TYPES = [
        ('diesel', 'Diesel'), ('essence', 'Essence'), ('hybride', 'Hybride'),
        ('electrique', 'Électrique'), ('gpl', 'GPL'),
    ]

    type_carburant = models.CharField(max_length=15, choices=TYPES)
    prix           = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix (FCFA / L)")
    date_effet     = models.DateField(verbose_name="Date d'effet")
    commentaire    = models.CharField(max_length=200, blank=True)
    created_by     = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='prix_carburant_saisis'
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Prix du carburant"
        verbose_name_plural = "Prix du carburant"
        ordering            = ['type_carburant', '-date_effet']
        unique_together     = [('type_carburant', 'date_effet')]

    def __str__(self):
        return f"{self.get_type_carburant_display()} — {self.prix} FCFA/L au {self.date_effet}"

    @classmethod
    def en_vigueur(cls, type_carburant, date):
        """Prix applicable à une date (None si aucun prix n'est défini)."""
        return (cls.objects
                .filter(type_carburant=type_carburant, date_effet__lte=date)
                .order_by('-date_effet').first())


from django.db.models.signals import post_delete  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_delete, sender=PleinsCarburant)
def _supprimer_depense_de_la_prise(sender, instance, **kwargs):
    """La dépense « Carburant » disparaît avec sa prise (suppression directe ou en cascade)."""
    from .depenses import supprimer_depense
    supprimer_depense(instance.pk)

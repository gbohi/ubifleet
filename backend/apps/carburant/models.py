"""UbiFleet — Carburant Models"""

from datetime import time as datetime_time
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


class PleinsCarburant(UbiFleetBaseModel):
    """Enregistrement d'un plein de carburant."""

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
    station = models.ForeignKey(
        Station, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pleins'
    )
    date_plein = models.DateField(verbose_name="Date du plein")
    heure_plein = models.TimeField(
        null=True, blank=True,
        verbose_name="Heure du plein"
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
        verbose_name="Kilométrage départ (km du plein précédent)"
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
    statut_validation = models.CharField(
        max_length=15, choices=StatutValidation.choices,
        default=StatutValidation.EN_ATTENTE
    )
    motif_anomalie = models.TextField(blank=True)
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
        verbose_name = "Plein de carburant"
        verbose_name_plural = "Pleins de carburant"
        ordering = ['-date_plein', '-created_at']

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.date_plein} — {self.volume_litres}L"

    def save(self, *args, **kwargs):
        # Auto-remplir prix_litre depuis paramètre si non renseigné
        if not self.prix_litre:
            try:
                from apps.parametrage.models import Parametre
                prix = Parametre.objects.filter(cle='prix_carburant_litre').first()
                if prix and prix.valeur:
                    from decimal import Decimal
                    self.prix_litre = Decimal(prix.valeur)
            except Exception:
                pass

        # Calcul automatique consommation + auto-remplir kilometrage_depart
        if self.kilometrage_releve and self.vehicule:
            from django.db.models import Q

            heure_actuelle = self.heure_plein or datetime_time.min

            dernier_plein = PleinsCarburant.objects.filter(
                vehicule=self.vehicule
            ).filter(
                Q(date_plein__lt=self.date_plein) |
                Q(date_plein=self.date_plein, heure_plein__lt=heure_actuelle)
            ).exclude(
                pk=self.pk
            ).order_by('-date_plein', '-heure_plein').first()

            if dernier_plein:
                # Auto-remplir km départ = km retour du plein précédent
                if not self.kilometrage_depart:
                    self.kilometrage_depart = dernier_plein.kilometrage_releve

                km_parcourus = self.kilometrage_releve - dernier_plein.kilometrage_releve
                if km_parcourus > 0:
                    self.consommation_calculee = round(
                        (float(self.volume_litres) / km_parcourus) * 100, 2
                    )
                    # Détection anomalie si conso > 30% au-dessus moyenne
                    moyenne = self.vehicule.consommation_moyenne()
                    if moyenne and float(self.consommation_calculee) > float(moyenne) * 1.3:
                        self.statut_validation = self.StatutValidation.ANOMALIE
                        self.motif_anomalie = (
                            f"Consommation anormale: {self.consommation_calculee} L/100km "
                            f"(moyenne: {moyenne} L/100km)"
                        )

        # MAJ kilométrage véhicule
        if self.vehicule and self.kilometrage_releve > self.vehicule.kilometrage_actuel:
            self.vehicule.kilometrage_actuel = self.kilometrage_releve
            self.vehicule.save(update_fields=['kilometrage_actuel'])

        super().save(*args, **kwargs)


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

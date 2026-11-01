"""UbiFleet — Budget & Comptabilité Models"""

from django.db import models
from apps.core.models import UbiFleetBaseModel


class BudgetAnnuel(UbiFleetBaseModel):
    """Budget annuel du parc automobile par agence."""
    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.CASCADE,
        related_name='budgets'
    )
    annee = models.PositiveSmallIntegerField()

    # Dotations par poste
    budget_carburant = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_entretien = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_reparations = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_assurances = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_pneumatiques = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_divers = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Budget annuel"
        unique_together = ['agence', 'annee']
        ordering = ['-annee']

    def __str__(self):
        return f"Budget {self.annee} — {self.agence.nom}"

    @property
    def budget_total(self):
        return (
            self.budget_carburant + self.budget_entretien +
            self.budget_reparations + self.budget_assurances +
            self.budget_pneumatiques + self.budget_divers
        )


class DepenseVehicule(UbiFleetBaseModel):
    """Ligne de dépense liée à un véhicule (pour rapport comptable)."""

    vehicule = models.ForeignKey(
        'vehicules.Vehicule', on_delete=models.SET_NULL,
        related_name='depenses', null=True, blank=True
    )
    agence = models.ForeignKey(
        'accounts.Agence', on_delete=models.PROTECT,
        related_name='depenses'
    )
    # Code d'une catégorie de Paramètres › Catégories de dépense
    categorie = models.CharField(max_length=20)
    date_depense = models.DateField()
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=300)
    fournisseur = models.CharField(max_length=150, blank=True)
    numero_facture = models.CharField(max_length=50, blank=True)
    fichier_justificatif = models.FileField(
        upload_to='budget/justificatifs/', null=True, blank=True
    )
    # Référence vers la source (plein, intervention, sinistre)
    ref_objet_type = models.CharField(max_length=50, blank=True)
    ref_objet_id = models.UUIDField(null=True, blank=True)

    class Meta:
        verbose_name = "Dépense véhicule"
        verbose_name_plural = "Dépenses véhicules"
        ordering = ['-date_depense']

    def __str__(self):
        immat = self.vehicule.immatriculation if self.vehicule else '—'
        return f"{immat} — {self.get_categorie_display()} — {self.montant} FCFA"

    def get_categorie_display(self):
        from apps.parametrage.models import CategorieDepense, libelles
        return libelles(CategorieDepense).get(self.categorie, self.categorie)

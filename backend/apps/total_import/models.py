"""UbiFleet — Transactions Carburant Total"""

import uuid
from django.db import models


class ImportTotal(models.Model):
    """Trace chaque import de fichier Total."""
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fichier_nom  = models.CharField(max_length=255)
    date_import  = models.DateTimeField(auto_now_add=True)
    nb_lignes    = models.IntegerField(default=0)
    nb_importees = models.IntegerField(default=0)
    nb_doublons  = models.IntegerField(default=0)
    nb_erreurs   = models.IntegerField(default=0)
    importé_par  = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        verbose_name        = "Import Total"
        verbose_name_plural = "Imports Total"
        ordering            = ['-date_import']

    def __str__(self):
        return f"Import {self.fichier_nom} — {self.date_import:%d/%m/%Y %H:%M}"


class TransactionCarburant(models.Model):
    """
    Table TRANSACTIONS_CARBURANT — 37 colonnes du fichier Total.
    Clé d'unicité : numero_ticket + code_autorisation + date_transaction
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Import source
    import_source = models.ForeignKey(
        ImportTotal, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions'
    )

    # ── Filiale & Client ──────────────────────────────────────────────
    numero_filiale  = models.CharField(max_length=50, blank=True)
    nom_filiale     = models.CharField(max_length=200, blank=True)
    numero_client   = models.CharField(max_length=50, blank=True)
    nom_client      = models.CharField(max_length=200, blank=True)

    # ── Moyen de paiement ─────────────────────────────────────────────
    numero_moyen_paiement    = models.CharField(max_length=100, blank=True)
    nom_titulaire_paiement   = models.CharField(max_length=200, blank=True)

    # ── Chauffeur & Véhicule ──────────────────────────────────────────
    numero_chauffeur         = models.CharField(max_length=50, blank=True)
    nom_chauffeur            = models.CharField(max_length=200, blank=True)
    immatriculation          = models.CharField(max_length=50, blank=True, db_index=True)
    kilometrage_precedent    = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    kilometrage_actuel       = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # ── Transaction ───────────────────────────────────────────────────
    date_transaction         = models.DateField(null=True, blank=True, db_index=True)
    heure_transaction        = models.TimeField(null=True, blank=True)
    numero_ticket            = models.CharField(max_length=100, blank=True, db_index=True)
    numero_station           = models.CharField(max_length=50, blank=True)
    nom_station              = models.CharField(max_length=200, blank=True)
    numero_terminal          = models.CharField(max_length=50, blank=True)
    nom_pompiste             = models.CharField(max_length=200, blank=True)
    type_transaction         = models.CharField(max_length=50, blank=True)
    nom_transaction          = models.CharField(max_length=200, blank=True)

    # ── Montants ──────────────────────────────────────────────────────
    montant_preautorise      = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    solde_avant              = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    nom_produit              = models.CharField(max_length=100, blank=True)
    prix_unitaire            = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volume                   = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    montant                  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    solde_apres              = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # ── Bonus ─────────────────────────────────────────────────────────
    bonus_mypass_utilise     = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    bonus_mypass_apres       = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # ── Technique ─────────────────────────────────────────────────────
    chrone_sam               = models.CharField(max_length=100, blank=True)
    atc                      = models.CharField(max_length=100, blank=True)
    profil_transaction       = models.CharField(max_length=100, blank=True)
    compteur_heures_precedent= models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    compteur_heures_actuel   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    nom_service              = models.CharField(max_length=100, blank=True)
    code_autorisation        = models.CharField(max_length=100, blank=True, db_index=True)
    statut_transaction       = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Transaction carburant Total"
        verbose_name_plural = "Transactions carburant Total"
        ordering            = ['-date_transaction', '-heure_transaction']
        # Clé d'unicité pour éviter les doublons
        constraints = [
            models.UniqueConstraint(
                fields=['numero_ticket', 'code_autorisation', 'date_transaction'],
                name='unique_transaction_total'
            )
        ]

    def __str__(self):
        return (f"{self.immatriculation} — {self.date_transaction} "
                f"{self.heure_transaction} — {self.montant} FCFA")

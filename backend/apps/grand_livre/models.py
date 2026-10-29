"""UbiFleet — Grand Livre Comptable"""
import uuid
from django.db import models


class ImportGrandLivre(models.Model):
    """Trace chaque import de fichier grand livre."""
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fichier_nom  = models.CharField(max_length=255)
    date_import  = models.DateTimeField(auto_now_add=True)
    nb_lignes    = models.IntegerField(default=0)
    nb_importees = models.IntegerField(default=0)
    nb_doublons  = models.IntegerField(default=0)
    nb_erreurs   = models.IntegerField(default=0)
    importe_par  = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Importé par"
    )

    class Meta:
        verbose_name        = "Import Grand Livre"
        verbose_name_plural = "Imports Grand Livre"
        ordering            = ['-date_import']

    def __str__(self):
        return f"Import {self.fichier_nom} — {self.date_import:%d/%m/%Y %H:%M}"


class LigneGrandLivre(models.Model):
    """
    Une ligne du grand livre comptable.
    Unicité : code_agence + compte + piece + no_ligne + date_analytique
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    import_source = models.ForeignKey(
        ImportGrandLivre, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes'
    )

    # ── Agence (ligne 2 du fichier) ──────────────────────────────────
    code_agence    = models.CharField(max_length=20, db_index=True, verbose_name="Code agence")
    libelle_agence = models.CharField(max_length=200, verbose_name="Libellé agence")

    # ── Compte ───────────────────────────────────────────────────────
    compte         = models.CharField(max_length=20, db_index=True, verbose_name="N° compte")
    libelle_compte = models.CharField(max_length=200, verbose_name="Libellé compte")

    # ── Dates ────────────────────────────────────────────────────────
    date_analytique = models.DateField(null=True, blank=True, verbose_name="Date analytique")
    date_comptable  = models.DateField(null=True, blank=True, verbose_name="Date comptable")

    # ── Identification ────────────────────────────────────────────────
    origine      = models.CharField(max_length=20, blank=True, verbose_name="Origine")
    piece        = models.CharField(max_length=50, blank=True, db_index=True, verbose_name="Pièce")
    no_ligne     = models.IntegerField(null=True, blank=True, verbose_name="N° ligne")
    no_analytique= models.IntegerField(null=True, blank=True, verbose_name="N° analytique")

    # ── Libellé ──────────────────────────────────────────────────────
    libelle_ecriture = models.CharField(max_length=255, blank=True, verbose_name="Libellé écriture")

    # ── Montants ─────────────────────────────────────────────────────
    debit  = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Débit")
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Crédit")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Ligne grand livre"
        verbose_name_plural = "Lignes grand livre"
        ordering            = ['code_agence', 'compte', 'date_analytique']
        constraints = [
            models.UniqueConstraint(
                fields=['code_agence', 'compte', 'piece', 'no_ligne', 'date_analytique'],
                name='unique_ligne_grand_livre'
            )
        ]

    def __str__(self):
        return f"{self.code_agence} | {self.compte} | {self.piece} | {self.debit}/{self.credit}"

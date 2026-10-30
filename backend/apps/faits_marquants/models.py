"""UbiFleet — Faits marquants (événements notables, avec pièce jointe)."""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from apps.core.models import UbiFleetBaseModel

EXTENSIONS_AUTORISEES = ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'txt']
TAILLE_MAX_MO = 10


def valider_taille(fichier):
    if fichier.size > TAILLE_MAX_MO * 1024 * 1024:
        raise ValidationError(f'Le document ne doit pas dépasser {TAILLE_MAX_MO} Mo.')


class FaitMarquant(UbiFleetBaseModel):
    libelle  = models.CharField(max_length=200, verbose_name="Libellé")
    date     = models.DateField()
    description = models.TextField(blank=True)
    document = models.FileField(
        upload_to='faits_marquants/%Y/', null=True, blank=True,
        validators=[FileExtensionValidator(EXTENSIONS_AUTORISEES), valider_taille],
    )
    agence   = models.ForeignKey(
        'accounts.Agence', null=True, blank=True, on_delete=models.PROTECT,
        related_name='faits_marquants',
        help_text="Vide = concerne toutes les agences (saisie réservée aux utilisateurs « Toutes les agences »).",
    )

    class Meta:
        verbose_name        = "Fait marquant"
        verbose_name_plural = "Faits marquants"
        ordering            = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} — {self.libelle}"

"""UbiFleet — Modèle de base abstrait"""

from django.db import models
import uuid


class UbiFleetBaseModel(models.Model):
    """Modèle abstrait partagé par toutes les entités UbiFleet."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    created_by = models.ForeignKey(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_created',
        verbose_name="Créé par"
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

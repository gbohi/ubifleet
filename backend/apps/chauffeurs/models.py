"""UbiFleet — Chauffeurs Models"""

from django.db import models
from apps.core.fichiers import VALIDATEURS_DOCUMENT, VALIDATEURS_PHOTO
from apps.core.models import UbiFleetBaseModel


class Chauffeur(UbiFleetBaseModel):

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        CONGE = 'conge', 'En congé'
        ABSENT = 'absent', 'Absent'
        SUSPENDU = 'suspendu', 'Suspendu'
        DEPART = 'depart', 'Départ'

    matricule = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    photo = models.ImageField(upload_to='chauffeurs/photos/', null=True, blank=True, validators=VALIDATEURS_PHOTO)

    numero_chauffeur_total = models.CharField(
        max_length=50, blank=True,
        verbose_name="N° chauffeur Total",
        help_text="Identifiant chauffeur dans la plateforme TotalEnergies — "
                  "sert à réconcilier les transactions importées avec ce chauffeur."
    )
    numero_permis = models.CharField(max_length=50)
    categories_permis = models.CharField(max_length=20, help_text="ex: B, B·C, B·C·D")
    date_obtention_permis = models.DateField(null=True, blank=True)
    date_expiration_permis = models.DateField(null=True, blank=True)

    agence = models.ForeignKey(
        'accounts.Agence',
        on_delete=models.PROTECT,
        related_name='chauffeurs'
    )
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.ACTIF
    )
    user = models.OneToOneField(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='chauffeur_profil'
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Chauffeur"
        verbose_name_plural = "Chauffeurs"
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.matricule} — {self.nom_complet}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"

    @property
    def permis_expire(self):
        if self.date_expiration_permis:
            from django.utils import timezone
            return self.date_expiration_permis < timezone.now().date()
        return False

    @property
    def jours_expiration_permis(self):
        if self.date_expiration_permis:
            from django.utils import timezone
            delta = self.date_expiration_permis - timezone.now().date()
            return delta.days
        return None


class DocumentChauffeur(UbiFleetBaseModel):
    """Document d'un chauffeur (permis scanné, pièce d'identité, contrat, visite
    médicale, photo…) : PDF, image ou bureautique, 10 Mo au plus."""
    chauffeur = models.ForeignKey(Chauffeur, on_delete=models.CASCADE, related_name='documents')
    # Code de Paramètres › Types de document chauffeur
    type_document = models.CharField(max_length=20)
    libelle = models.CharField(max_length=150, blank=True, help_text="Précision libre (ex. « Recto-verso »).")
    numero = models.CharField(max_length=100, blank=True)
    date_emission = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)
    fichier = models.FileField(upload_to='chauffeurs/documents/%Y/', validators=VALIDATEURS_DOCUMENT)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Document chauffeur"
        verbose_name_plural = "Documents chauffeur"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.chauffeur.nom_complet} — {self.get_type_document_display()}"

    def get_type_document_display(self):
        from apps.parametrage.models import TypeDocumentChauffeur, libelles
        return libelles(TypeDocumentChauffeur).get(self.type_document, self.type_document)

    @property
    def est_expire(self):
        from django.utils import timezone
        return bool(self.date_expiration and self.date_expiration < timezone.localdate())

    @property
    def jours_restants(self):
        from django.utils import timezone
        return (self.date_expiration - timezone.localdate()).days if self.date_expiration else None

"""UbiFleet — Contrôle des fichiers envoyés (documents, images)."""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

EXTENSIONS_DOCUMENTS = ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'txt']
EXTENSIONS_IMAGES = ['jpg', 'jpeg', 'png', 'webp']
TAILLE_MAX_DOCUMENT_MO = 10
TAILLE_MAX_PHOTO_MO = 5


def valider_taille_document(fichier):
    if fichier.size > TAILLE_MAX_DOCUMENT_MO * 1024 * 1024:
        raise ValidationError(f'Le fichier ne doit pas dépasser {TAILLE_MAX_DOCUMENT_MO} Mo.')


def valider_taille_photo(fichier):
    if fichier.size > TAILLE_MAX_PHOTO_MO * 1024 * 1024:
        raise ValidationError(f'La photo ne doit pas dépasser {TAILLE_MAX_PHOTO_MO} Mo.')


VALIDATEURS_DOCUMENT = [FileExtensionValidator(EXTENSIONS_DOCUMENTS), valider_taille_document]
VALIDATEURS_PHOTO = [FileExtensionValidator(EXTENSIONS_IMAGES), valider_taille_photo]

"""UbiFleet — Outils communs aux référentiels (statuts, marques, assureurs...)."""

from django.db.models import Count, ProtectedError
from rest_framework import serializers, status
from rest_framework.response import Response


def annoter_utilisations(qs, relation, filtre=None):
    """Ajoute `nb_utilisations` : nombre d'objets qui référencent chaque ligne."""
    return qs.annotate(nb_utilisations=Count(relation, filter=filtre, distinct=True))


class NbUtilisationsField(serializers.IntegerField):
    """Compteur `nb_utilisations` annoté par la vue (0 si absent, ex. création)."""

    def __init__(self, **kwargs):
        super().__init__(read_only=True, default=0, **kwargs)


class SuppressionProtegeeMixin:
    """Refuse la suppression d'un élément encore utilisé, avec un message
    explicite, au lieu de vider silencieusement le champ des véhicules
    (SET_NULL) ou de renvoyer une erreur 500 (PROTECT).

    `relations_utilisation` : [(related_name, libellé au pluriel), ...]
    """
    relations_utilisation = ()

    def utilisations(self, obj):
        """[(nombre, libellé)] — à redéfinir pour un comptage sans relation."""
        return [(getattr(obj, relation).count(), libelle)
                for relation, libelle in self.relations_utilisation]

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        usages = [f'{n} {libelle}' for n, libelle in self.utilisations(obj) if n]
        if usages:
            return Response(
                {'detail': f"Suppression impossible : utilisé par {', '.join(usages)}. "
                           "Désactivez-le plutôt : il restera sur les données existantes "
                           "mais ne sera plus proposé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': "Suppression impossible : cet élément est encore utilisé. "
                           "Désactivez-le plutôt."},
                status=status.HTTP_400_BAD_REQUEST,
            )


def valider_code_referentiel(modele, code, actuel=None, libelle='Valeur'):
    """Contrôle un code saisi pour un référentiel paramétrable : il doit exister
    et être actif (une valeur désactivée reste acceptée si elle est déjà
    enregistrée sur la donnée modifiée)."""
    from rest_framework.exceptions import ValidationError
    if code == actuel and code:
        return code
    obj = modele.objects.filter(code=code).first()
    if not obj:
        raise ValidationError(f"{libelle} inconnu(e) : « {code} ». Voir Paramètres.")
    if not obj.actif:
        raise ValidationError(f"{libelle} « {obj.libelle} » désactivé(e) dans Paramètres.")
    return code

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

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        usages = []
        for relation, libelle in self.relations_utilisation:
            n = getattr(obj, relation).count()
            if n:
                usages.append(f'{n} {libelle}')
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

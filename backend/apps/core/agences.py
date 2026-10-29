"""UbiFleet — Cloisonnement des données par agence.

Règle unique, indépendante du rôle :
- un utilisateur rattaché à une agence ne voit, ne crée et ne modifie que
  les données de son agence ;
- un utilisateur sans agence (« Toutes les agences ») voit tout.

Le rôle détermine CE QUE l'on peut faire (permissions), l'agence
détermine SUR QUELLES DONNÉES.
"""

from rest_framework.exceptions import PermissionDenied

MESSAGE_AUTRE_AGENCE = "Ces données appartiennent à une autre agence que la vôtre."

# Champs d'écriture rattachés (directement ou non) à une agence
CHAMPS_RATTACHES = ('vehicule', 'chauffeur', 'fiche', 'intervention', 'demande',
                    'sinistre', 'tournee', 'station')


def voit_toutes_agences(user) -> bool:
    return user.agence_id is None


def filtrer_par_agence(qs, user, champ='agence'):
    """Restreint un queryset à l'agence de l'utilisateur.
    `champ` : chemin vers l'agence, ex. 'agence' ou 'vehicule__agence'."""
    if voit_toutes_agences(user):
        return qs
    return qs.filter(**{champ: user.agence_id})


def agence_effective(user, agence_demandee=None):
    """Identifiant d'agence à appliquer à un filtre issu d'un paramètre de
    requête (?agence=) : celle de l'utilisateur s'il est rattaché."""
    if voit_toutes_agences(user):
        return agence_demandee or None
    return str(user.agence_id)


def agence_pour_creation(user, agence=None):
    """Agence à enregistrer sur une nouvelle donnée : celle de l'utilisateur
    s'il est rattaché (refus s'il en demande une autre)."""
    if voit_toutes_agences(user):
        return agence
    if agence is not None and agence.pk != user.agence_id:
        raise PermissionDenied(MESSAGE_AUTRE_AGENCE)
    return user.agence


def controler_agence(user, data):
    """Refuse une écriture qui référence une agence, ou un objet (véhicule,
    chauffeur, fiche...) d'une agence autre que celle de l'utilisateur."""
    if voit_toutes_agences(user):
        return
    agence = data.get('agence')
    if agence is not None and agence.pk != user.agence_id:
        raise PermissionDenied(MESSAGE_AUTRE_AGENCE)
    for champ in CHAMPS_RATTACHES:
        obj = data.get(champ)
        agence_id = getattr(obj, 'agence_id', None)
        if agence_id is not None and agence_id != user.agence_id:
            raise PermissionDenied(MESSAGE_AUTRE_AGENCE)


def filtrer_transactions_total(qs, user):
    """Transactions TotalEnergies : rattachées à l'agence par son numéro
    client Total (Agence.numero_client_total)."""
    if voit_toutes_agences(user):
        return qs
    numero = (user.agence.numero_client_total or '').strip()
    return qs.filter(numero_client=numero) if numero else qs.none()


def filtrer_grand_livre(qs, user):
    """Lignes du grand livre : rattachées à l'agence par son code."""
    if voit_toutes_agences(user):
        return qs
    return qs.filter(code_agence__iexact=user.agence.code)


class AgenceMixin:
    """ViewSet dont les données sont cloisonnées par agence.

    - `champ_agence` : chemin vers l'agence pour filtrer le queryset ;
    - les créations et modifications sont contrôlées (agence et objets
      rattachés), et l'agence est imposée à la création si le modèle a un
      champ `agence` (`agence_a_la_creation = True`).

    Les ViewSets qui redéfinissent perform_create / perform_update doivent
    appeler self.controler_ecriture(serializer).
    """
    champ_agence = 'agence'
    agence_a_la_creation = False

    def filtrer_agence(self, qs):
        return filtrer_par_agence(qs, self.request.user, self.champ_agence)

    def controler_ecriture(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)

    def perform_create(self, serializer):
        self.controler_ecriture(serializer)
        if self.agence_a_la_creation:
            agence = agence_pour_creation(self.request.user, serializer.validated_data.get('agence'))
            serializer.save(agence=agence)
        else:
            serializer.save()

    def perform_update(self, serializer):
        self.controler_ecriture(serializer)
        serializer.save()

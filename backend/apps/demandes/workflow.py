"""UbiFleet — Opérations du workflow réutilisables hors de l'API des demandes."""
from .models import Demande, ValidationDemande


def soumettre(demande):
    """Passe une demande en validation au niveau 1 et prévient les validateurs."""
    from .views import _creer_alerte_demande
    demande.statut        = Demande.Statut.SOUMISE
    demande.niveau_actuel = 1
    demande.save()
    ValidationDemande.objects.get_or_create(
        demande=demande, niveau=1,
        defaults={'decision': ValidationDemande.Decision.EN_ATTENTE}
    )
    _creer_alerte_demande(demande, 1)
    return demande

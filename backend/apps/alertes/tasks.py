"""UbiFleet — Génération d'alertes (Celery + appel direct)"""

import datetime
from django.utils import timezone


PRIORITE_PAR_NIVEAU = {
    'attention': 'normale',
    'urgent':    'haute',
    'depasse':   'critique',
}


def _signaler(niveau_echeance, cible, type_alerte, defaults):
    """Crée / met à jour l'alerte active d'une échéance, avec la priorité
    correspondant à son niveau (attention, urgent, dépassé)."""
    from apps.alertes.models import Alerte
    defaults = {**defaults, 'priorite': PRIORITE_PAR_NIVEAU[niveau_echeance],
                'statut': Alerte.Statut.ACTIVE}
    Alerte.objects.update_or_create(
        **cible, type_alerte=type_alerte,
        statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE],
        defaults=defaults,
    )


def _check_documents():
    """
    Documents véhicule (assurance, CT, carte de transport, vignette) : alerte
    selon les seuils de chaque échéance (Paramètres › Échéances). Seul le
    document le plus récent de chaque type compte pour un véhicule.
    Appelable directement (sans Celery) et via @shared_task.
    """
    from apps.vehicules.models import DocumentVehicule, TypeDocumentVehicule
    from apps.alertes.models import Alerte
    from apps.parametrage.echeances import DEPASSE, OK, NC, niveau, tous_les_seuils

    today  = timezone.now().date()
    seuils = tous_les_seuils()

    # Code document → (type alerte « expire bientôt », type « expiré », libellé)
    CODE_MAP = {
        TypeDocumentVehicule.CODE_ASSURANCE:       (Alerte.TypeAlerte.ASSURANCE_EXPIRATION,
                                                    Alerte.TypeAlerte.ASSURANCE_EXPIREE,
                                                    'Assurance'),
        TypeDocumentVehicule.CODE_CT:              (Alerte.TypeAlerte.CT_EXPIRATION,
                                                    Alerte.TypeAlerte.CT_EXPIREE,
                                                    'Contrôle technique'),
        TypeDocumentVehicule.CODE_CARTE_TRANSPORT: ('carte_transport_exp',
                                                    'carte_transport_expiree',
                                                    'Carte de transport'),
        TypeDocumentVehicule.CODE_VIGNETTE:        ('vignette_exp',
                                                    'vignette_expiree',
                                                    'Vignette'),
    }

    # Document le plus récent par (véhicule, type)
    derniers = {}
    for doc in (DocumentVehicule.objects
                .filter(date_expiration__isnull=False, type_document__code__in=CODE_MAP,
                        vehicule__is_active=True)
                .select_related('vehicule', 'vehicule__agence', 'type_document')):
        k = (doc.vehicule_id, doc.type_document.code)
        if k not in derniers or doc.date_expiration > derniers[k].date_expiration:
            derniers[k] = doc

    for (_, code), doc in derniers.items():
        type_exp, type_expire, label = CODE_MAP[code]
        jours = (doc.date_expiration - today).days
        niv   = niveau(jours, *seuils[code])
        if niv in (OK, NC):
            continue
        v = doc.vehicule
        if niv == DEPASSE:
            _signaler(niv, {'vehicule': v}, type_expire, {
                'titre':   f'{label} EXPIRÉ — {v.immatriculation}',
                'message': (f"Le document « {label} » du véhicule {v.immatriculation} "
                            f"a expiré le {doc.date_expiration}. Renouvellement urgent requis."),
                'agence': v.agence, 'date_echeance': doc.date_expiration,
            })
        else:
            _signaler(niv, {'vehicule': v}, type_exp, {
                'titre':   f'{label} expire J-{jours} — {v.immatriculation}',
                'message': (f"Le document « {label} » du véhicule {v.immatriculation} "
                            f"expire le {doc.date_expiration} (dans {jours} jour(s))."),
                'agence': v.agence, 'date_echeance': doc.date_expiration,
            })


def _check_vehicule_km():
    """Révision : alerte dès le seuil urgent (km restants), critique une
    fois le kilométrage de révision dépassé."""
    from apps.vehicules.models import Vehicule
    from apps.alertes.models import Alerte
    from apps.parametrage.echeances import URGENT, DEPASSE, niveau, seuils

    attention, urgent = seuils('revision')
    for v in Vehicule.objects.filter(is_active=True, kilometrage_revision__gt=0).select_related('agence'):
        restant = v.kilometrage_revision - v.kilometrage_actuel
        niv = niveau(restant, attention, urgent)
        if niv not in (URGENT, DEPASSE):
            continue
        message = (
            f'Le véhicule {v.immatriculation} a dépassé son kilométrage de révision '
            f'({v.kilometrage_actuel} km / prévu {v.kilometrage_revision} km).'
            if niv == DEPASSE else
            f'Révision du véhicule {v.immatriculation} dans {restant} km '
            f'({v.kilometrage_actuel} km / prévu {v.kilometrage_revision} km).'
        )
        _signaler(niv, {'vehicule': v}, Alerte.TypeAlerte.REVISION_DUE, {
            'titre': f'Révision {"dépassée" if niv == DEPASSE else "à prévoir"} — {v.immatriculation}',
            'message': message, 'agence': v.agence,
        })


def _check_pneus():
    """Pneus en service : alerte dès le seuil urgent avant le kilométrage
    de remplacement prévu."""
    from apps.entretien.models import SuiviPneus
    from apps.alertes.models import Alerte
    from apps.parametrage.echeances import URGENT, DEPASSE, niveau, seuils

    attention, urgent = seuils('pneus')
    for p in (SuiviPneus.objects
              .filter(statut='en_service', kilometrage_remplacement__isnull=False,
                      vehicule__is_active=True)
              .select_related('vehicule', 'vehicule__agence')):
        v = p.vehicule
        restant = p.kilometrage_remplacement - v.kilometrage_actuel
        niv = niveau(restant, attention, urgent)
        if niv not in (URGENT, DEPASSE):
            continue
        _signaler(niv, {'vehicule': v}, Alerte.TypeAlerte.PNEU_USURE, {
            'titre': f'Pneu à changer — {v.immatriculation} ({p.get_position_display()})',
            'message': (f'Pneu {p.get_position_display()} du véhicule {v.immatriculation} : '
                        f'remplacement prévu à {p.kilometrage_remplacement} km, '
                        f'véhicule à {v.kilometrage_actuel} km.'),
            'agence': v.agence,
        })


def _check_permis():
    """Permis des chauffeurs actifs, selon l'échéance « Permis de conduire »."""
    from apps.chauffeurs.models import Chauffeur
    from apps.alertes.models import Alerte
    from apps.parametrage.echeances import DEPASSE, OK, NC, niveau, seuils

    today = timezone.now().date()
    attention, urgent = seuils('permis')
    for c in Chauffeur.objects.filter(
        date_expiration_permis__isnull=False,
        date_expiration_permis__lte=today + datetime.timedelta(days=attention),
        statut=Chauffeur.Statut.ACTIF,
    ).select_related('agence'):
        jours = (c.date_expiration_permis - today).days
        niv = niveau(jours, attention, urgent)
        if niv in (OK, NC):
            continue
        expire = niv == DEPASSE
        _signaler(niv, {'chauffeur': c},
                  Alerte.TypeAlerte.PERMIS_EXPIRE if expire else Alerte.TypeAlerte.PERMIS_EXPIRATION, {
            'titre': (f'Permis EXPIRÉ — {c.nom_complet}' if expire
                      else f'Permis expire J-{jours} — {c.nom_complet}'),
            'message': (f"Le permis du chauffeur {c.nom_complet} ({c.matricule}) "
                        f"{'a expiré' if expire else 'expire'} le {c.date_expiration_permis}."),
            'agence': c.agence, 'date_echeance': c.date_expiration_permis,
        })


def run_all_checks_sync():
    """Exécution synchrone — appelée depuis la view sans Celery."""
    _check_documents()
    _check_vehicule_km()
    _check_pneus()
    _check_permis()


# ── Wrappers Celery (optionnels si Celery est installé) ──────────────
try:
    from celery import shared_task

    @shared_task
    def check_documents_alerts():
        _check_documents()

    @shared_task
    def check_vehicule_alerts(vehicule_id=None):
        _check_vehicule_km()

    @shared_task
    def check_permis_alerts():
        _check_permis()

    @shared_task
    def check_pneus_alerts():
        _check_pneus()

    @shared_task
    def run_all_checks():
        run_all_checks_sync()

except ImportError:
    pass

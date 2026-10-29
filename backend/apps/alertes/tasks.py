"""UbiFleet — Génération d'alertes (Celery + appel direct)"""

import datetime
from django.utils import timezone


def _check_documents():
    """
    Vérifie les DocumentVehicule (assurance, CT, carte_transport, vignette)
    et crée / met à jour les alertes d'expiration.
    Appelable directement (sans Celery) et via @shared_task.
    """
    from apps.vehicules.models import DocumentVehicule, TypeDocumentVehicule
    from apps.alertes.models import Alerte
    from apps.parametrage.models import Parametre

    today   = timezone.now().date()
    j_urgent   = int(Parametre.get('etat_parc_jours_urgent',     7))
    j_attention= int(Parametre.get('etat_parc_jours_attention', 30))

    # Codes réservés → type_alerte correspondant
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

    docs = (
        DocumentVehicule.objects
        .filter(date_expiration__isnull=False)
        .select_related('vehicule', 'vehicule__agence', 'type_document')
    )

    for doc in docs:
        code = doc.type_document.code
        if code not in CODE_MAP:
            continue  # Autres types → pas d'alerte automatique

        type_exp, type_expire, label = CODE_MAP[code]
        jours = (doc.date_expiration - today).days
        v     = doc.vehicule

        if jours < 0:
            # Document expiré
            Alerte.objects.update_or_create(
                vehicule=v,
                type_alerte=type_expire,
                statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE],
                defaults={
                    'titre':        f'{label} EXPIRÉ — {v.immatriculation}',
                    'message':      (
                        f"Le document « {label} » du véhicule {v.immatriculation} "
                        f"a expiré le {doc.date_expiration}. "
                        f"Renouvellement urgent requis."
                    ),
                    'priorite':     Alerte.Priorite.CRITIQUE,
                    'agence':       v.agence,
                    'date_echeance':doc.date_expiration,
                    'statut':       Alerte.Statut.ACTIVE,
                }
            )
        elif jours <= j_urgent:
            priorite = Alerte.Priorite.CRITIQUE
            Alerte.objects.update_or_create(
                vehicule=v,
                type_alerte=type_exp,
                statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE],
                defaults={
                    'titre':        f'{label} expire J-{jours} — {v.immatriculation}',
                    'message':      (
                        f"Le document « {label} » du véhicule {v.immatriculation} "
                        f"expire le {doc.date_expiration} (dans {jours} jour(s))."
                    ),
                    'priorite':     priorite,
                    'agence':       v.agence,
                    'date_echeance':doc.date_expiration,
                    'statut':       Alerte.Statut.ACTIVE,
                }
            )
        elif jours <= j_attention:
            priorite = Alerte.Priorite.HAUTE
            Alerte.objects.update_or_create(
                vehicule=v,
                type_alerte=type_exp,
                statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE],
                defaults={
                    'titre':        f'{label} expire J-{jours} — {v.immatriculation}',
                    'message':      (
                        f"Le document « {label} » du véhicule {v.immatriculation} "
                        f"expire le {doc.date_expiration} (dans {jours} jour(s))."
                    ),
                    'priorite':     priorite,
                    'agence':       v.agence,
                    'date_echeance':doc.date_expiration,
                    'statut':       Alerte.Statut.ACTIVE,
                }
            )


def _check_vehicule_km():
    from apps.vehicules.models import Vehicule
    from apps.alertes.models import Alerte
    qs = Vehicule.objects.filter(is_active=True)
    for v in qs:
        if v.revision_due:
            Alerte.objects.get_or_create(
                vehicule=v,
                type_alerte=Alerte.TypeAlerte.REVISION_DUE,
                statut=Alerte.Statut.ACTIVE,
                defaults={
                    'titre':    f'Révision due — {v.immatriculation}',
                    'message':  (
                        f'Le véhicule {v.immatriculation} a dépassé son kilométrage '
                        f'de révision ({v.kilometrage_actuel} km / prévu {v.kilometrage_revision} km).'
                    ),
                    'priorite': Alerte.Priorite.CRITIQUE,
                    'agence':   v.agence,
                }
            )


def _check_permis():
    from apps.chauffeurs.models import Chauffeur
    from apps.parametrage.models import Parametre
    from apps.alertes.models import Alerte
    today   = timezone.now().date()
    nb_jours = int(Parametre.get('alerte_permis_jours', 60))
    horizon  = today + datetime.timedelta(days=nb_jours)
    for c in Chauffeur.objects.filter(
        date_expiration_permis__lte=horizon,
        date_expiration_permis__gte=today,
        statut=Chauffeur.Statut.ACTIF,
    ).select_related('agence'):
        jours = (c.date_expiration_permis - today).days
        Alerte.objects.update_or_create(
            chauffeur=c,
            type_alerte=Alerte.TypeAlerte.PERMIS_EXPIRATION,
            statut__in=[Alerte.Statut.ACTIVE, Alerte.Statut.LUE],
            defaults={
                'titre':        f'Permis expire J-{jours} — {c.nom_complet}',
                'message':      (
                    f"Le permis du chauffeur {c.nom_complet} ({c.matricule}) "
                    f"expire le {c.date_expiration_permis}."
                ),
                'priorite':     Alerte.Priorite.HAUTE if jours <= nb_jours // 2 else Alerte.Priorite.NORMALE,
                'agence':       c.agence,
                'date_echeance':c.date_expiration_permis,
                'statut':       Alerte.Statut.ACTIVE,
            }
        )


def run_all_checks_sync():
    """Exécution synchrone — appelée depuis la view sans Celery."""
    _check_documents()
    _check_vehicule_km()
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
    def run_all_checks():
        _check_documents()
        _check_vehicule_km()
        _check_permis()

except ImportError:
    pass

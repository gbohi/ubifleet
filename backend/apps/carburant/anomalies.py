"""UbiFleet — Consommation des prises de carburant et détection des anomalies.

Méthode « plein à plein » : la consommation d'une prise est son volume
rapporté aux km parcourus depuis la prise précédente du véhicule
(ordre chronologique : date, heure, saisie).

Une prise est anormale si sa consommation dépasse la consommation de
référence du véhicule de plus du seuil paramétré (Paramètres › Seuils).
La référence est la consommation moyenne des AUTRES prises du véhicule
(litres ÷ km), pour que la prise contrôlée ne se compare pas à elle-même ;
il en faut au moins MIN_PRISES_REFERENCE pour juger.

Chaque prise anormale ouvre une alerte « Consommation anormale » pour son
agence ; l'alerte est mise à jour si la prise est corrigée, et clôturée
automatiquement si la consommation redevient normale.
"""

from dataclasses import dataclass
from datetime import datetime, time as datetime_time, timezone as dt_timezone

from django.utils import timezone

MIN_PRISES_REFERENCE = 3


@dataclass
class Evaluation:
    depart: int | None          # km de la prise précédente
    km: int | None              # km parcourus depuis la prise précédente
    conso: float | None         # L/100 km
    reference: float | None     # consommation de référence du véhicule
    motif: str                  # vide si la consommation est normale


def ordre_chronologique(p):
    """Clé de tri des prises : date, heure (sans heure = en fin de journée), saisie."""
    return (p.date_plein, p.heure_plein is None, p.heure_plein or datetime_time.min,
            p.created_at or datetime.max.replace(tzinfo=dt_timezone.utc))


def _nombre(x):
    return f"{x:,.2f}".replace(',', ' ').replace('.', ',')


def evaluer(prises):
    """{pk: Evaluation} pour des prises d'un même véhicule, triées par ordre_chronologique."""
    from apps.carburant.models import PleinsCarburant
    from apps.parametrage.echeances import seuil_conso_anomalie

    intervalles, precedent = [], None
    for p in prises:
        km = None
        if precedent and p.kilometrage_releve > precedent.kilometrage_releve:
            km = p.kilometrage_releve - precedent.kilometrage_releve
        intervalles.append((p, precedent.kilometrage_releve if precedent else None, km))
        precedent = p

    # Prises qui entrent dans la référence (une prise rejetée n'en fait pas partie)
    comptees = {p.pk: (float(p.volume_litres), km) for p, _, km in intervalles
                if km and p.statut_validation != PleinsCarburant.StatutValidation.REJETE}
    total_litres = sum(v for v, _ in comptees.values())
    total_km = sum(k for _, k in comptees.values())
    seuil = seuil_conso_anomalie()

    resultat = {}
    for p, depart, km in intervalles:
        conso = round(float(p.volume_litres) / km * 100, 2) if km else None
        litres, km_ref, n = total_litres, total_km, len(comptees)
        if p.pk in comptees:
            litres -= comptees[p.pk][0]
            km_ref -= comptees[p.pk][1]
            n -= 1
        reference = round(litres / km_ref * 100, 2) if n >= MIN_PRISES_REFERENCE and km_ref > 0 else None
        motif = ''
        if conso is not None and reference and conso > reference * (1 + seuil / 100):
            ecart = round((conso / reference - 1) * 100)
            motif = (f"Consommation de {_nombre(conso)} L/100 km, soit {ecart} % au-dessus de la "
                     f"moyenne du véhicule ({_nombre(reference)} L/100 km ; seuil : {seuil:g} %).")
        resultat[p.pk] = Evaluation(depart, km, conso, reference, motif)
    return resultat


def prises_du_vehicule(vehicule):
    from apps.carburant.models import PleinsCarburant
    return sorted(PleinsCarburant.objects.filter(vehicule=vehicule), key=ordre_chronologique)


def statut_et_motif(prise, ev):
    """Statut à appliquer : une prise rejetée le reste."""
    S = prise.StatutValidation
    if prise.statut_validation == S.REJETE:
        return prise.statut_validation, prise.motif_anomalie
    return (S.ANOMALIE, ev.motif) if ev.motif else (S.VALIDE, '')


def synchroniser_alerte(prise, ev):
    """Ouvre, met à jour ou clôture l'alerte « Consommation anormale » de la prise.

    Une alerte déjà traitée ou ignorée n'est rouverte que si le constat a
    changé : date, volume ou km parcourus (prise ou prise précédente corrigée)."""
    from apps.alertes.models import Alerte
    alerte = Alerte.objects.filter(plein=prise).order_by('-created_at').first()
    ouverte = alerte is not None and alerte.statut in (Alerte.Statut.ACTIVE, Alerte.Statut.LUE)

    if prise.statut_validation != prise.StatutValidation.ANOMALIE:
        if ouverte:
            alerte.statut = Alerte.Statut.TRAITEE
            alerte.date_traitement = timezone.now()
            alerte.notes_traitement = ("Clôturée automatiquement : après correction, la consommation "
                                       "de la prise de carburant n'est plus anormale.")
            alerte.save(update_fields=['statut', 'date_traitement', 'notes_traitement', 'updated_at'])
        return

    v = prise.vehicule
    quand = f"{prise.date_plein:%d/%m/%Y}" + (f" à {prise.heure_plein:%H:%M}" if prise.heure_plein else '')
    km = f"{ev.km:,}".replace(',', ' ')
    constat = (f"Prise de carburant du {quand} : {_nombre(float(prise.volume_litres))} L pour "
               f"{km} km parcourus depuis la prise précédente.")
    message = (f"{constat} {prise.motif_anomalie} Vérifiez le volume et le kilométrage saisis ; "
               "s'ils sont exacts, recherchez une fuite, une panne ou une utilisation anormale.")
    champs = {
        'type_alerte': Alerte.TypeAlerte.CONSO_ANORMALE,
        'priorite': Alerte.Priorite.HAUTE,
        'titre': f"Consommation anormale — {v.immatriculation}",
        'message': message,
        'vehicule': v,
        'chauffeur': prise.chauffeur,
        'agence': prise.agence,
    }
    if alerte is None:
        Alerte.objects.create(plein=prise, statut=Alerte.Statut.ACTIVE, **champs)
        return
    if not ouverte and alerte.message.startswith(constat):
        return
    for k, val in champs.items():
        setattr(alerte, k, val)
    if not ouverte:
        alerte.statut = Alerte.Statut.ACTIVE
        alerte.traitee_par, alerte.date_traitement, alerte.notes_traitement = None, None, ''
    alerte.save()

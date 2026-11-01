"""UbiFleet — Consommation des prises de carburant et détection des anomalies.

Méthode « plein à plein » : la consommation d'une prise est son volume
rapporté aux km parcourus depuis la prise précédente du véhicule
(ordre chronologique : date, heure, saisie).

Une prise est anormale si la consommation de la FENÊTRE qu'elle termine
(elle et les prises précédentes, N au total : litres et km cumulés)
dépasse la consommation de référence du véhicule de plus du seuil
(Paramètres › Seuils : N = 3 et 40 % par défaut). Juger plusieurs prises
ensemble lisse les remplissages partiels : 20 L puis un complément de 60 L
paraissent anormaux pris un par un, pas ensemble. La référence est la
consommation moyenne des AUTRES prises du véhicule (hors fenêtre jugée),
pour que les prises contrôlées ne se comparent pas à elles-mêmes ; il en
faut au moins MIN_PRISES_REFERENCE pour juger.

Un kilométrage incohérent est lui-même une anomalie : compteur inférieur à
celui de la prise précédente, ou plus de KM_MAX_INTERVALLE km depuis (erreur
de saisie probable). Ces intervalles n'entrent pas dans la référence (un seul
compteur erroné la faussait pour toutes les prises du véhicule) ; la prise
suivante se calcule depuis la dernière prise au kilométrage cohérent. Les
consommations hors de [CONSO_MIN, CONSO_MAX] L/100 km ne comptent pas non
plus dans la référence.

Chaque prise anormale ouvre une alerte « Consommation anormale » pour son
agence ; l'alerte est mise à jour si la prise est corrigée, et clôturée
automatiquement si la consommation redevient normale.
"""

from dataclasses import dataclass
from datetime import datetime, time as datetime_time, timezone as dt_timezone

from django.utils import timezone

MIN_PRISES_REFERENCE = 3
KM_MAX_INTERVALLE = 2000          # km entre deux prises au-delà desquels le compteur est jugé erroné
CONSO_MIN, CONSO_MAX = 2.0, 60.0  # L/100 km plausibles pour entrer dans la référence


@dataclass
class Evaluation:
    depart: int | None          # km de la prise précédente
    km: int | None              # km parcourus depuis la prise précédente
    conso: float | None         # L/100 km
    reference: float | None     # consommation de référence du véhicule
    motif: str                  # vide si la consommation est normale
    km_incoherent: bool = False  # compteur incohérent avec la prise précédente


def ordre_chronologique(p):
    """Clé de tri des prises : date, heure (sans heure = en fin de journée), saisie."""
    return (p.date_plein, p.heure_plein is None, p.heure_plein or datetime_time.min,
            p.created_at or datetime.max.replace(tzinfo=dt_timezone.utc))


def _km(x):
    return f"{x:,} km".replace(',', ' ')


def _nombre(x):
    return f"{x:,.2f}".replace(',', ' ').replace('.', ',')


def evaluer(prises):
    """{pk: Evaluation} pour des prises d'un même véhicule, triées par ordre_chronologique."""
    from apps.carburant.models import PleinsCarburant
    from apps.parametrage.echeances import fenetre_conso_anomalie, seuil_conso_anomalie

    # Intervalles : depuis la dernière prise au kilométrage cohérent ; les litres
    # d'une prise écartée sont reportés sur l'intervalle suivant (ils ont été
    # consommés sur ces km).
    intervalles, precedent, reportes = [], None, 0.0
    for p in prises:
        km, incoherent = None, ''
        if precedent:
            ecart = p.kilometrage_releve - precedent.kilometrage_releve
            if not p.kilometrage_releve:
                incoherent = "Kilométrage non renseigné (0 km) : saisissez le compteur relevé à la prise."
            elif ecart < 0:
                incoherent = (f"Kilométrage saisi ({_km(p.kilometrage_releve)}) inférieur à celui de la prise "
                              f"précédente ({_km(precedent.kilometrage_releve)}) : vérifiez le compteur.")
            elif ecart > KM_MAX_INTERVALLE:
                incoherent = (f"{_km(ecart)} parcourus depuis la prise précédente ({_km(precedent.kilometrage_releve)}) : "
                              f"kilométrage probablement erroné (plus de {_km(KM_MAX_INTERVALLE)}), vérifiez le compteur.")
            elif ecart > 0:
                km = ecart
        litres = float(p.volume_litres)
        if incoherent:
            reportes += litres
        elif km:
            litres, reportes = litres + reportes, 0.0
        intervalles.append((p, precedent.kilometrage_releve if precedent else None, km, incoherent, litres))
        if not incoherent:
            precedent = p

    # Prises qui entrent dans la référence : intervalle cohérent, consommation plausible,
    # prise non rejetée
    comptees = {p.pk: (litres, km) for p, _, km, _, litres in intervalles
                if km and CONSO_MIN <= litres / km * 100 <= CONSO_MAX
                and p.statut_validation != PleinsCarburant.StatutValidation.REJETE}
    total_litres = sum(v for v, _ in comptees.values())
    total_km = sum(k for _, k in comptees.values())
    seuil = seuil_conso_anomalie()
    fenetre = fenetre_conso_anomalie()

    resultat, recents = {}, []   # recents : derniers intervalles cohérents (pk, litres, km)
    for p, depart, km, incoherent, litres_intervalle in intervalles:
        conso = round(litres_intervalle / km * 100, 2) if km else None
        if km:
            recents = (recents + [(p.pk, litres_intervalle, km)])[-fenetre:]
        # Fenêtre jugée : cette prise et les précédentes (litres et km cumulés : un
        # remplissage partiel suivi d'un complément se compensent)
        groupe = recents if km else []
        litres_f = sum(l for _, l, _ in groupe)
        km_f = sum(k for _, _, k in groupe)
        conso_f = litres_f / km_f * 100 if km_f else None
        # Référence : moyenne des autres prises du véhicule (hors fenêtre jugée)
        litres, km_ref, n = total_litres, total_km, len(comptees)
        for pk, _, _ in groupe:
            if pk in comptees:
                litres -= comptees[pk][0]
                km_ref -= comptees[pk][1]
                n -= 1
        reference = round(litres / km_ref * 100, 2) if n >= MIN_PRISES_REFERENCE and km_ref > 0 else None
        motif = incoherent
        if not motif and conso_f is not None and reference and conso_f > reference * (1 + seuil / 100):
            ecart = round((conso_f / reference - 1) * 100)
            sur = (f"sur les {len(groupe)} dernières prises ({_nombre(litres_f)} L pour {_km(km_f)})"
                   if len(groupe) > 1 else f"sur cette prise ({_nombre(litres_f)} L pour {_km(km_f)})")
            motif = (f"Consommation de {_nombre(conso_f)} L/100 km {sur}, soit {ecart} % au-dessus de la "
                     f"moyenne du véhicule ({_nombre(reference)} L/100 km ; seuil : {seuil:g} %).")
        resultat[p.pk] = Evaluation(depart, km, conso, reference, motif, bool(incoherent))
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
    if ev.km_incoherent or not ev.km:
        constat = f"Prise de carburant du {quand} : {_nombre(float(prise.volume_litres))} L, compteur {_km(prise.kilometrage_releve)}."
        message = f"{constat} {prise.motif_anomalie}"
    else:
        constat = (f"Prise de carburant du {quand} : {_nombre(float(prise.volume_litres))} L pour "
                   f"{_km(ev.km)} parcourus depuis la prise précédente.")
        message = (f"{constat} {prise.motif_anomalie} Vérifiez le volume et le kilométrage saisis ; "
                   "s'ils sont exacts, recherchez une fuite, une panne ou une utilisation anormale.")
    champs = {
        'type_alerte': Alerte.TypeAlerte.CONSO_ANORMALE,
        'priorite': Alerte.Priorite.HAUTE,
        'titre': (f"Kilométrage incohérent — {v.immatriculation}" if ev.km_incoherent
                  else f"Consommation anormale — {v.immatriculation}"),
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

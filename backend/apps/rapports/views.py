"""UbiFleet — Rapports & Statistiques Views"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
import datetime

from apps.accounts.permissions import IsOperateur, IsFleetManager
from apps.core.agences import agence_effective, voit_toutes_agences


def agence_autorisee(request):
    """Agence à appliquer aux rapports : un utilisateur rattaché à une agence
    ne voit que la sienne, quel que soit le paramètre ?agence= transmis."""
    return agence_effective(request.user, request.query_params.get('agence'))


class DashboardDGView(APIView):
    """
    Tableau de bord complet pour la Direction Générale.
    GET /rapports/dashboard/
    Paramètres: ?mois=5&annee=2025&agence=<uuid>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.vehicules.models import Vehicule
        from apps.carburant.models import PleinsCarburant
        from apps.entretien.models import Intervention
        from apps.sinistres.models import Sinistre, ContratAssurance
        from apps.alertes.models import Alerte
        from apps.budget.models import DepenseVehicule

        mois = int(request.query_params.get('mois', timezone.now().month))
        annee = int(request.query_params.get('annee', timezone.now().year))
        agence_id = agence_autorisee(request)

        agence_filter = {}
        if agence_id:
            agence_filter['agence_id'] = agence_id

        # Parc
        vehicules = Vehicule.objects.filter(is_active=True, **agence_filter)
        parc = {
            'total': vehicules.count(),
            'en_service': vehicules.filter(statut__code='en_service').count(),
            'en_revision': vehicules.filter(statut__code='en_revision').count(),
            'immobilises': vehicules.filter(statut__code__in=['immobilise', 'en_panne', 'accidente']).count(),
        }

        # Carburant du mois
        pleins = PleinsCarburant.objects.filter(
            date_plein__month=mois,
            date_plein__year=annee,
            **agence_filter
        )
        from apps.carburant.analyses import classement_ecarts, consommation_vehicules, conso_ponderee
        carburant = pleins.aggregate(
            volume=Sum('volume_litres'),
            montant=Sum('montant_fcfa'),
            nb_pleins=Count('id'),
        )
        # Conso pondérée par les km (méthode plein à plein) et véhicules au-dessus de leur référence
        conso_lignes = consommation_vehicules(list(pleins.select_related(
            'vehicule__agence', 'vehicule__marque', 'vehicule__modele')))
        carburant['conso_moy'] = conso_ponderee(conso_lignes)
        carburant['anomalies'] = pleins.filter(statut_validation='anomalie').count()
        top_ecart_conso = [{
            'vehicule__immatriculation': l['immatriculation'], 'vehicule__marque': l['marque'],
            'vehicule__modele': l['modele'], 'conso': l['conso_moyenne'], 'reference': l['conso_reference'],
            'ecart_pct': l['ecart_pct'], 'litres': l['litres'],
        } for l in classement_ecarts(conso_lignes)]

        # Entretiens du mois
        interventions = Intervention.objects.filter(
            date_planifiee__month=mois,
            date_planifiee__year=annee,
            **agence_filter
        )
        entretien = {
            'planifiees': interventions.count(),
            'terminees': interventions.filter(statut='termine').count(),
            'en_cours': interventions.filter(statut='en_cours').count(),
            'cout': interventions.filter(statut='termine').aggregate(
                total=Sum('cout_reel')
            )['total'] or 0,
        }

        # Sinistres
        sinistres = Sinistre.objects.filter(**agence_filter)
        sinistr = {
            'en_cours': sinistres.filter(
                statut__in=['declare', 'en_instruction', 'expertise', 'reparation']
            ).count(),
            'annee': sinistres.filter(date_sinistre__year=annee).count(),
        }

        # Alertes actives
        alertes_qs = Alerte.objects.filter(statut='active', **agence_filter)
        alertes = {
            'total': alertes_qs.count(),
            'critiques': alertes_qs.filter(priorite='critique').count(),
            'hautes': alertes_qs.filter(priorite='haute').count(),
        }

        # Coûts mensuels (12 derniers mois)
        cout_mensuel = []
        for i in range(11, -1, -1):
            d = timezone.now().date().replace(day=1) - datetime.timedelta(days=i * 30)
            m, a = d.month, d.year
            total = DepenseVehicule.objects.filter(
                date_depense__month=m, date_depense__year=a, **agence_filter
            ).aggregate(total=Sum('montant'))['total'] or 0
            cout_mensuel.append({'mois': m, 'annee': a, 'total': float(total)})

        # Consommation top 10 véhicules
        top_conso = list(
            pleins.values('vehicule__immatriculation', 'vehicule__marque__libelle', 'vehicule__modele__libelle')
                  .annotate(litres=Sum('volume_litres'), montant=Sum('montant_fcfa'))
                  .order_by('-litres')[:10]
        )

        # Répartition des coûts du mois par catégorie (données réelles)
        depenses_mois = DepenseVehicule.objects.filter(
            date_depense__month=mois, date_depense__year=annee, **agence_filter
        )
        repartition_qs = (
            depenses_mois.values('categorie')
            .annotate(total=Sum('montant'))
            .order_by('-total')
        )
        from apps.parametrage.models import CategorieDepense, libelles
        categorie_labels = libelles(CategorieDepense)
        repartition_couts = [
            {
                'categorie': item['categorie'],
                'label': categorie_labels.get(item['categorie'], item['categorie']),
                'montant': float(item['total'] or 0),
            }
            for item in repartition_qs if item['total']
        ]

        # Assurances expirant
        horizon_30 = timezone.now().date() + datetime.timedelta(days=30)
        assurances_critiques = ContratAssurance.objects.filter(
            date_fin__lte=horizon_30,
            is_active=True,
            vehicule__agence_id__in=vehicules.values_list('agence_id', flat=True)
        ).count()

        return Response({
            'periode': {'mois': mois, 'annee': annee},
            'parc': parc,
            'carburant': carburant,
            'entretien': entretien,
            'sinistres': sinistr,
            'alertes': alertes,
            'cout_mensuel': cout_mensuel,
            'top_consommation': top_conso,
            'top_ecart_conso': top_ecart_conso,
            'repartition_couts': repartition_couts,
            'assurances_critiques': assurances_critiques,
        })


class RapportCarburantView(APIView):
    """Rapport détaillé carburant."""
    permission_classes = [IsOperateur]

    def get(self, request):
        from apps.carburant.models import PleinsCarburant
        from apps.vehicules.models import Vehicule

        mois = int(request.query_params.get('mois', timezone.now().month))
        annee = int(request.query_params.get('annee', timezone.now().year))
        agence_id = agence_autorisee(request)

        qs = PleinsCarburant.objects.filter(date_plein__month=mois, date_plein__year=annee)
        if agence_id:
            qs = qs.filter(agence_id=agence_id)

        from apps.carburant.analyses import consommation_vehicules, conso_ponderee
        par_vehicule = list(
            qs.values(
                'vehicule__id', 'vehicule__immatriculation', 'vehicule__marque__libelle',
                'vehicule__modele__libelle', 'vehicule__type_carburant',
                'agence__nom'
            ).annotate(
                total_litres=Sum('volume_litres'),
                total_fcfa=Sum('montant_fcfa'),
                nb_pleins=Count('id'),
            ).order_by('-total_litres')
        )
        # Conso pondérée par les km (méthode plein à plein), référence et écart par véhicule
        conso_lignes = consommation_vehicules(list(qs.select_related(
            'vehicule__agence', 'vehicule__marque', 'vehicule__modele')))
        par_id = {l['vehicule_id']: l for l in conso_lignes}
        for v in par_vehicule:
            l = par_id.get(str(v.pop('vehicule__id')), {})
            v['conso_moy'] = l.get('conso_moyenne')
            v['conso_reference'] = l.get('conso_reference')
            v['ecart_pct'] = l.get('ecart_pct')

        par_station = list(
            qs.filter(station__isnull=False)
              .values('station__nom')
              .annotate(total=Sum('montant_fcfa'), litres=Sum('volume_litres'))
              .order_by('-total')[:10]
        )

        anomalies = list(
            qs.filter(statut_validation='anomalie')
              .values(
                  'vehicule__immatriculation', 'date_plein',
                  'consommation_calculee', 'volume_litres', 'montant_fcfa'
              )
        )

        global_agg = qs.aggregate(
            total_litres=Sum('volume_litres'),
            total_fcfa=Sum('montant_fcfa'),
            nb_pleins=Count('id')
        )
        global_agg['conso_moy'] = conso_ponderee(conso_lignes)

        return Response({
            'periode': {'mois': mois, 'annee': annee},
            'global': global_agg,
            'par_vehicule': par_vehicule,
            'par_station': par_station,
            'anomalies': anomalies,
        })


class RapportCoutsView(APIView):
    """Coûts annuels : total et comparaison avec l'année précédente, évolution
    mensuelle, budget prévu / réalisé par poste, répartition par catégorie,
    origine et agence, véhicules les plus coûteux (détail par poste)."""
    permission_classes = [IsOperateur]

    def get(self, request):
        from apps.budget.etat import postes_des_categories, recapitulatif
        from apps.budget.models import BudgetAnnuel, DepenseVehicule
        from apps.parametrage.models import CategorieDepense
        from apps.vehicules.models import Vehicule

        annee = int(request.query_params.get('annee', timezone.now().year))
        agence_id = agence_autorisee(request)
        base = DepenseVehicule.objects.all()
        budgets = BudgetAnnuel.objects.filter(annee=annee)
        vehicules = Vehicule.objects.filter(is_active=True)
        if agence_id:
            base = base.filter(agence_id=agence_id)
            budgets = budgets.filter(agence_id=agence_id)
            vehicules = vehicules.filter(agence_id=agence_id)
        qs = base.filter(date_depense__year=annee)
        qs_prec = base.filter(date_depense__year=annee - 1)
        recap = recapitulatif(qs)
        total = recap['total']
        total_prec = float(qs_prec.aggregate(t=Sum('montant'))['t'] or 0)

        # Évolution mensuelle, avec l'année précédente et le cumul
        def par_mois(q):
            return {r['date_depense__month']: float(r['t'] or 0)
                    for r in q.order_by().values('date_depense__month').annotate(t=Sum('montant'))}
        mois_n, mois_p = par_mois(qs), par_mois(qs_prec)
        aujourd_hui = timezone.localdate()
        cumul = 0.0
        evolution = []
        for m in range(1, 13):
            cumul += mois_n.get(m, 0.0)
            a_venir = annee > aujourd_hui.year or (annee == aujourd_hui.year and m > aujourd_hui.month)
            evolution.append({'mois': m, 'total': mois_n.get(m, 0.0), 'total_precedent': mois_p.get(m, 0.0),
                              'cumul': None if a_venir else cumul})   # pas de cumul sur les mois à venir

        # Budget prévu / réalisé par poste
        postes = CategorieDepense.PosteBudget
        prevus = budgets.aggregate(**{p: Sum(f'budget_{p}') for p in postes.values})
        realises = {p['poste']: p['total'] for p in recap['par_poste']}
        budget = []
        for code, libelle in postes.choices:
            prevu, realise = float(prevus.get(code) or 0), realises.get(code, 0.0)
            budget.append({'poste': code, 'libelle': libelle, 'prevu': prevu, 'realise': realise,
                           'ecart': prevu - realise, 'taux': round(realise * 100 / prevu, 1) if prevu else None})
        budget_total = sum(b['prevu'] for b in budget)

        # Véhicules les plus coûteux, détaillés par poste
        poste_de = postes_des_categories()
        detail = {}
        for r in qs.exclude(vehicule=None).order_by().values(
                'vehicule_id', 'vehicule__immatriculation', 'vehicule__marque__libelle',
                'vehicule__modele__libelle', 'categorie').annotate(t=Sum('montant')):
            v = detail.setdefault(r['vehicule_id'], {
                'immatriculation': r['vehicule__immatriculation'],
                'designation': ' '.join(x for x in (r['vehicule__marque__libelle'], r['vehicule__modele__libelle']) if x),
                'total': 0.0, 'postes': {}})
            montant = float(r['t'] or 0)
            poste = poste_de.get(r['categorie'], 'divers')
            v['total'] += montant
            v['postes'][poste] = v['postes'].get(poste, 0.0) + montant
        top = sorted(detail.values(), key=lambda v: -v['total'])[:15]
        nb_vehicules = vehicules.count()

        par_agence = [{'agence': r['agence__nom'], 'code': r['agence__code'], 'nb': r['nb'], 'total': float(r['t'] or 0),
                       'part': round(float(r['t'] or 0) * 100 / total, 1) if total else 0}
                      for r in qs.order_by().values('agence__nom', 'agence__code')
                                 .annotate(nb=Count('id'), t=Sum('montant')).order_by('-t')]
        return Response({
            'annee': annee,
            'total': total, 'nb': recap['nb'],
            'total_precedent': total_prec,
            'variation': round((total - total_prec) * 100 / total_prec, 1) if total_prec else None,
            'budget_total': budget_total,
            'taux_budget': round(total * 100 / budget_total, 1) if budget_total else None,
            'nb_vehicules': nb_vehicules,
            'cout_moyen_vehicule': round(total / nb_vehicules) if nb_vehicules else None,
            'evolution': evolution,
            'budget': budget,
            'par_poste': recap['par_poste'],
            'par_categorie': recap['par_categorie'],
            'par_origine': recap['par_origine'],
            'par_agence': par_agence,
            'top_vehicules': top,
            'postes': [{'poste': c, 'libelle': l} for c, l in postes.choices],
        })


class RapportMultiAgencesView(APIView):
    """Comparaison des performances entre agences."""
    permission_classes = [IsFleetManager]

    def get(self, request):
        from apps.vehicules.models import Vehicule
        from apps.carburant.models import PleinsCarburant
        from apps.budget.models import DepenseVehicule
        from apps.accounts.models import Agence

        annee = int(request.query_params.get('annee', timezone.now().year))
        agences = Agence.objects.filter(is_active=True)
        if not voit_toutes_agences(request.user):
            agences = agences.filter(pk=request.user.agence_id)
        result = []

        for agence in agences:
            vehicules = Vehicule.objects.filter(agence=agence, is_active=True)
            nb_v = vehicules.count()
            if nb_v == 0:
                continue

            cout = DepenseVehicule.objects.filter(
                agence=agence, date_depense__year=annee
            ).aggregate(total=Sum('montant'))['total'] or 0

            carb = PleinsCarburant.objects.filter(
                agence=agence, date_plein__year=annee
            ).aggregate(litres=Sum('volume_litres'), montant=Sum('montant_fcfa'))

            result.append({
                'agence_id': str(agence.id),
                'agence_nom': agence.nom,
                'agence_code': agence.code,
                'nb_vehicules': nb_v,
                'cout_total': float(cout),
                'cout_par_vehicule': round(float(cout) / nb_v, 0) if nb_v else 0,
                'carburant_litres': float(carb['litres'] or 0),
                'carburant_fcfa': float(carb['montant'] or 0),
            })

        return Response({'annee': annee, 'agences': result})


class RapportSinistresView(APIView):
    """Statistiques sinistres par type et par mois."""
    permission_classes = [IsOperateur]

    def get(self, request):
        from apps.sinistres.models import Sinistre
        from apps.vehicules.models import Vehicule

        date_debut    = request.query_params.get('date_debut')
        date_fin      = request.query_params.get('date_fin')
        immatriculation = request.query_params.get('immatriculation', '').strip()
        agence_id     = agence_autorisee(request)
        chauffeur_id  = request.query_params.get('chauffeur')

        qs = Sinistre.objects.all()
        if date_debut:
            qs = qs.filter(date_sinistre__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_sinistre__lte=date_fin)
        if immatriculation:
            qs = qs.filter(vehicule__immatriculation__icontains=immatriculation)
        if agence_id:
            qs = qs.filter(agence_id=agence_id)
        if chauffeur_id:
            qs = qs.filter(chauffeur_id=chauffeur_id)

        # Par type
        par_type = list(
            qs.values('type_sinistre')
              .annotate(nb=Count('id'), cout=Sum('cout_reparation'))
              .order_by('-nb')
        )

        # Par mois
        par_mois = list(
            qs.values('date_sinistre__year', 'date_sinistre__month')
              .annotate(nb=Count('id'), cout=Sum('cout_reparation'))
              .order_by('date_sinistre__year', 'date_sinistre__month')
        )

        # Par statut
        par_statut = list(
            qs.values('statut').annotate(nb=Count('id')).order_by('-nb')
        )

        from apps.parametrage.models import TypeSinistre, libelles
        TYPE_LABELS = libelles(TypeSinistre)
        MOIS_LABELS = ['Jan','Fév','Mar','Avr','Mai','Jun',
                       'Jul','Aoû','Sep','Oct','Nov','Déc']

        for r in par_type:
            r['libelle'] = TYPE_LABELS.get(r['type_sinistre'], r['type_sinistre'])
            r['cout'] = float(r['cout'] or 0)
        for r in par_mois:
            r['mois_nom'] = MOIS_LABELS[r['date_sinistre__month'] - 1]
            r['cout'] = float(r['cout'] or 0)

        return Response({
            'total': qs.count(),
            'par_type': par_type,
            'par_mois': par_mois,
            'par_statut': par_statut,
        })


class RapportInterventionsView(APIView):
    """Statistiques interventions/entretien par type et par mois."""
    permission_classes = [IsOperateur]

    def get(self, request):
        from apps.entretien.models import Intervention

        date_debut      = request.query_params.get('date_debut')
        date_fin        = request.query_params.get('date_fin')
        immatriculation = request.query_params.get('immatriculation', '').strip()
        agence_id       = agence_autorisee(request)
        categorie       = request.query_params.get('categorie')

        qs = Intervention.objects.select_related('type_intervention')
        if date_debut:
            qs = qs.filter(date_planifiee__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_planifiee__lte=date_fin)
        if immatriculation:
            qs = qs.filter(vehicule__immatriculation__icontains=immatriculation)
        if agence_id:
            qs = qs.filter(agence_id=agence_id)
        if categorie:
            qs = qs.filter(type_intervention__categorie=categorie)

        # Par catégorie de type
        par_categorie = list(
            qs.values('type_intervention__categorie')
              .annotate(nb=Count('id'), cout=Sum('cout_reel'))
              .order_by('-nb')
        )
        CAT_LABELS = {
            'preventif': 'Entretien préventif', 'curatif': 'Réparation curative',
            'pneus': 'Pneus', 'carrosserie': 'Carrosserie',
            'controle': 'Contrôle réglementaire', 'autre': 'Autre',
        }
        for r in par_categorie:
            r['libelle'] = CAT_LABELS.get(r['type_intervention__categorie'] or '', 'Autre')
            r['cout'] = float(r['cout'] or 0)

        # Par type d'intervention
        par_type = list(
            qs.values('type_intervention__nom', 'type_intervention__categorie')
              .annotate(nb=Count('id'), cout=Sum('cout_reel'))
              .order_by('-nb')[:20]
        )
        for r in par_type:
            r['cout'] = float(r['cout'] or 0)

        # Par mois
        par_mois = list(
            qs.values('date_planifiee__year', 'date_planifiee__month')
              .annotate(nb=Count('id'), cout=Sum('cout_reel'))
              .order_by('date_planifiee__year', 'date_planifiee__month')
        )
        MOIS_LABELS = ['Jan','Fév','Mar','Avr','Mai','Jun',
                       'Jul','Aoû','Sep','Oct','Nov','Déc']
        for r in par_mois:
            r['mois_nom'] = MOIS_LABELS[r['date_planifiee__month'] - 1]
            r['cout'] = float(r['cout'] or 0)

        # Par statut
        par_statut = list(
            qs.values('statut').annotate(nb=Count('id')).order_by('-nb')
        )

        return Response({
            'total': qs.count(),
            'cout_total': float(qs.filter(statut='termine')
                                  .aggregate(t=Sum('cout_reel'))['t'] or 0),
            'par_categorie': par_categorie,
            'par_type': par_type,
            'par_mois': par_mois,
            'par_statut': par_statut,
        })


class RapportPneusView(APIView):
    """Statistiques pneus par statut, position et par mois."""
    permission_classes = [IsOperateur]

    def get(self, request):
        from apps.entretien.models import SuiviPneus

        date_debut      = request.query_params.get('date_debut')
        date_fin        = request.query_params.get('date_fin')
        immatriculation = request.query_params.get('immatriculation', '').strip()
        agence_id       = agence_autorisee(request)

        qs = SuiviPneus.objects.select_related('vehicule', 'vehicule__agence')
        if date_debut:
            qs = qs.filter(date_montage__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_montage__lte=date_fin)
        if immatriculation:
            qs = qs.filter(vehicule__immatriculation__icontains=immatriculation)
        if agence_id:
            qs = qs.filter(vehicule__agence_id=agence_id)

        # Par statut
        par_statut = list(
            qs.values('statut').annotate(nb=Count('id'), cout=Sum('cout')).order_by('-nb')
        )
        STATUT_LABELS = {
            'en_service': 'En service', 'a_changer': 'À changer', 'change': 'Changé',
        }
        for r in par_statut:
            r['libelle'] = STATUT_LABELS.get(r['statut'], r['statut'])
            r['cout'] = float(r['cout'] or 0)

        # Par position
        par_position = list(
            qs.values('position').annotate(nb=Count('id'), cout=Sum('cout')).order_by('position')
        )
        POS_LABELS = {
            'av_gauche': 'Avant gauche', 'av_droit': 'Avant droit',
            'ar_gauche': 'Arrière gauche', 'ar_droit': 'Arrière droit',
            'secours': 'Secours',
        }
        for r in par_position:
            r['libelle'] = POS_LABELS.get(r['position'], r['position'])
            r['cout'] = float(r['cout'] or 0)

        # Par marque
        par_marque = list(
            qs.exclude(marque='').values('marque')
              .annotate(nb=Count('id'), cout=Sum('cout'))
              .order_by('-nb')[:10]
        )
        for r in par_marque: r['cout'] = float(r['cout'] or 0)

        # Par mois (date_montage)
        par_mois = list(
            qs.values('date_montage__year', 'date_montage__month')
              .annotate(nb=Count('id'), cout=Sum('cout'))
              .order_by('date_montage__year', 'date_montage__month')
        )
        MOIS_LABELS = ['Jan','Fév','Mar','Avr','Mai','Jun',
                       'Jul','Aoû','Sep','Oct','Nov','Déc']
        for r in par_mois:
            r['mois_nom'] = MOIS_LABELS[r['date_montage__month'] - 1]
            r['cout'] = float(r['cout'] or 0)

        # À changer bientôt (dans les 5000 km)
        urgents = list(
            qs.filter(statut='a_changer')
              .values('vehicule__immatriculation', 'position', 'marque',
                      'kilometrage_remplacement')
              .order_by('kilometrage_remplacement')[:20]
        )
        for r in urgents:
            r['position_libelle'] = POS_LABELS.get(r['position'], r['position'])

        return Response({
            'total': qs.count(),
            'cout_total': float(qs.aggregate(t=Sum('cout'))['t'] or 0),
            'par_statut': par_statut,
            'par_position': par_position,
            'par_marque': par_marque,
            'par_mois': par_mois,
            'urgents': urgents,
        })


class RapportEffectifParcView(APIView):
    """
    GET /rapports/effectif-parc/
    Nombre de véhicules groupés par : agence, marque, modèle, type,
    carburant, statut, affectation/usage.
    Filtres optionnels : agence, actif (défaut: véhicules actifs uniquement)
    """
    permission_classes = [IsOperateur]

    def get(self, request):
        from apps.vehicules.models import Vehicule

        qs = Vehicule.objects.all()

        # Filtre actif (par défaut : uniquement les véhicules actifs)
        actif = request.query_params.get('actif', 'true')
        if actif.lower() == 'true':
            qs = qs.filter(is_active=True)

        # Filtre agence (paramètre ou restriction utilisateur)
        agence_id = agence_autorisee(request)
        if agence_id:
            qs = qs.filter(agence_id=agence_id)

        total = qs.count()

        def grouper(queryset, champ_valeur, champ_libelle=None):
            """Groupe et compte, retourne [{label, nb, pct}] trié par nb desc."""
            rows = (
                queryset.values(champ_valeur, *( [champ_libelle] if champ_libelle else [] ))
                .annotate(nb=Count('id'))
                .order_by('-nb')
            )
            out = []
            for r in rows:
                label = r.get(champ_libelle) if champ_libelle else r.get(champ_valeur)
                if label is None or label == '':
                    label = 'Non renseigné'
                out.append({
                    'label': str(label),
                    'nb': r['nb'],
                    'pct': round(r['nb'] / total * 100, 1) if total else 0,
                })
            return out

        # Types véhicule / carburant : mapper les codes vers les libellés display
        type_labels = dict(Vehicule._meta.get_field('type_vehicule').choices or [])
        carb_labels = dict(Vehicule._meta.get_field('type_carburant').choices or [])

        par_type = grouper(qs, 'type_vehicule')
        for r in par_type:
            r['label'] = str(type_labels.get(r['label'], r['label']))

        par_carburant = grouper(qs, 'type_carburant')
        for r in par_carburant:
            r['label'] = str(carb_labels.get(r['label'], r['label']))

        return Response({
            'total': total,
            'par_agence':    grouper(qs, 'agence__id',      'agence__nom'),
            'par_marque':    grouper(qs, 'marque__id',      'marque__libelle'),
            'par_modele':    grouper(qs, 'modele__id',      'modele__libelle'),
            'par_type':      par_type,
            'par_carburant': par_carburant,
            'par_statut':    grouper(qs, 'statut__id',      'statut__libelle'),
            'par_usage':     grouper(qs, 'affectation__id', 'affectation__libelle'),
        })

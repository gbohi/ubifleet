"""UbiFleet — Carburant Views"""

from datetime import timedelta
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters import rest_framework as df
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Avg, Count, Q, Prefetch

from .models import (
    PleinsCarburant, DotationCarburant, Station, RapprochementCarburant, PrixCarburant, TourneeEffectuee,
)
from . import analyses, suivi, tournees
from apps.parametrage.models import TypeMouvement
from .serializers import (
    PleinSerializer,
    DotationSerializer, StationSerializer, RapprochementSerializer, PrixCarburantSerializer,
)
from apps.accounts.permissions import IsFleetManager, RoleBasedPermission
from apps.core.referentiels import SuppressionProtegeeMixin, annoter_utilisations
from apps.parametrage.corrections import SaisieCorrigeableMixin
from apps.parametrage.fenetre_saisie import (
    ACTION_HORS_DELAI, CARBURANT, fenetre, tracer_hors_delai,
)
from apps.core.agences import (
    AgenceMixin, agence_pour_creation, controler_agence,
    filtrer_par_agence, filtrer_transactions_total, voit_toutes_agences,
)


class PleinFilter(FilterSet):
    vehicule = df.UUIDFilter()
    agence = df.UUIDFilter()
    statut_validation = df.ChoiceFilter(choices=PleinsCarburant.StatutValidation.choices)
    date_min = df.DateFilter(field_name='date_plein', lookup_expr='gte')
    date_max = df.DateFilter(field_name='date_plein', lookup_expr='lte')
    mois = df.NumberFilter(field_name='date_plein__month')
    annee = df.NumberFilter(field_name='date_plein__year')

    class Meta:
        model = PleinsCarburant
        fields = ['vehicule', 'agence', 'chauffeur', 'station', 'type_mouvement', 'tournee_effectuee']


class PleinViewSet(SaisieCorrigeableMixin, viewsets.ModelViewSet):
    """
    CRUD pleins de carburant.
    GET  /carburant/pleins/anomalies/      — liste des anomalies
    GET  /carburant/pleins/stats/          — statistiques carburant
    GET  /carburant/pleins/consommation/   — rapport consommation par véhicule
    """
    serializer_class = PleinSerializer
    parser_classes   = [MultiPartParser, FormParser, JSONParser]
    # Fenêtre de saisie et journal des corrections (cf. parametrage.corrections)
    domaine_saisie = CARBURANT
    champ_date     = 'date_plein'
    champs_journal = ('vehicule', 'chauffeur', 'type_mouvement', 'tournee', 'station', 'date_plein', 'heure_plein',
                      'volume_litres', 'prix_litre', 'montant_fcfa', 'kilometrage_releve',
                      'bon_carburant', 'agence', 'notes', 'photo_tableau_bord')
    module   = 'carburant'
    role_map = {
            'list': 'operateur',
            'retrieve': 'operateur',
            'create': 'operateur',
            'update': 'gestionnaire',
            'partial_update': 'gestionnaire',
            'destroy': 'responsable_flotte',
            'anomalies': 'operateur',
            ACTION_HORS_DELAI: 'responsable_flotte',   # droit complémentaire, cf. fenetre_saisie
    }

    def get_permissions(self):
        return [RoleBasedPermission()]

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PleinFilter
    search_fields = ['vehicule__immatriculation', 'bon_carburant', 'station__nom']
    ordering_fields = ['date_plein', 'montant_fcfa', 'volume_litres', 'consommation_calculee']
    ordering = ['-date_plein']

    def get_queryset(self):
        qs = PleinsCarburant.objects.select_related(
            'vehicule', 'chauffeur', 'station', 'agence', 'valide_par', 'tournee', 'tournee_effectuee'
        )
        return filtrer_par_agence(qs, self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        data = serializer.validated_data
        controler_agence(user, data)
        vehicule = data.get('vehicule')
        agence = agence_pour_creation(user, data.get('agence') or (vehicule and vehicule.agence))
        extra = {}
        if fenetre(user, CARBURANT).controler_date(data['date_plein'], 'date_plein'):
            extra.update(tracer_hors_delai(user))
        # Prix non saisi : prix en vigueur à la date du plein pour le carburant du véhicule
        if not data.get('prix_litre') and data.get('vehicule'):
            prix = PrixCarburant.en_vigueur(data['vehicule'].type_carburant, data['date_plein'])
            if prix:
                extra['prix_litre'] = prix.prix
                if not data.get('montant_fcfa'):
                    extra['montant_fcfa'] = round(prix.prix * data['volume_litres'], 2)
        cloturer_te = serializer.validated_data.pop('cloturer_tournee', False)
        commentaire = serializer.validated_data.pop('commentaire_tournee', '')
        if cloturer_te:
            tournees.exiger_droit(user, tournees.ACTION_CLOTURER, 'clôturer')
        plein = serializer.save(created_by=user, agence=agence, **extra)
        # Tournée : rattachement à la tournée en cours ou ouverture d'une nouvelle
        if plein.type_mouvement == TypeMouvement.CODE_TOURNEE:
            te = plein.tournee_effectuee or tournees.ouvrir(plein, user)
            tournees.actualiser(te)
            if cloturer_te:
                te.refresh_from_db()
                tournees.cloturer(te, user, commentaire=commentaire)
        # Une prise antérieure à d'autres change la consommation des suivantes
        self.apres_correction([plein.vehicule], [plein.date_plein])

    @transaction.atomic
    def perform_update(self, serializer):
        cloturer_te = serializer.validated_data.pop('cloturer_tournee', False)
        commentaire = serializer.validated_data.pop('commentaire_tournee', '')
        te = serializer.instance.tournee_effectuee
        if cloturer_te and te and te.statut == te.Statut.EN_COURS:
            tournees.exiger_droit(self.request.user, tournees.ACTION_CLOTURER, 'clôturer')
        super().perform_update(serializer)
        if te:
            tournees.actualiser_par_id(te.pk)
            te.refresh_from_db()
            if cloturer_te and te.statut == te.Statut.EN_COURS:
                tournees.cloturer(te, self.request.user, commentaire=commentaire)

    @transaction.atomic
    def perform_destroy(self, instance):
        te_id = instance.tournee_effectuee_id
        super().perform_destroy(instance)
        tournees.actualiser_par_id(te_id)

    @action(detail=False, methods=['get'])
    def anomalies(self, request):
        """Pleins avec anomalies de consommation."""
        qs = self.get_queryset().filter(
            statut_validation=PleinsCarburant.StatutValidation.ANOMALIE
        )
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques carburant (filtrable par mois/année/agence)."""
        qs = self.get_queryset()
        mois = request.query_params.get('mois')
        annee = request.query_params.get('annee')
        if mois:
            qs = qs.filter(date_plein__month=mois)
        if annee:
            qs = qs.filter(date_plein__year=annee)

        agg = qs.aggregate(
            total_litres=Sum('volume_litres'),
            total_montant=Sum('montant_fcfa'),
            nb_pleins=Count('id'),
            conso_moyenne=Avg('consommation_calculee'),
        )
        agg['nb_anomalies'] = qs.filter(
            statut_validation=PleinsCarburant.StatutValidation.ANOMALIE
        ).count()

        par_vehicule = list(
            qs.values(
                'vehicule__immatriculation', 'vehicule__marque', 'vehicule__modele'
            ).annotate(
                litres=Sum('volume_litres'),
                montant=Sum('montant_fcfa'),
                conso_moy=Avg('consommation_calculee'),
                nb=Count('id')
            ).order_by('-litres')[:10]
        )

        return Response({'agregats': agg, 'top_vehicules': par_vehicule})

    # ── Analyses (onglets Consommation, Évolution, Rapprochement Total) ──
    def _periode(self, requis=True):
        from rest_framework import serializers as s
        q = self.request.query_params
        try:
            debut = s.DateField().to_internal_value(q['date_debut']) if q.get('date_debut') else None
            fin = s.DateField().to_internal_value(q['date_fin']) if q.get('date_fin') else None
        except s.ValidationError:
            raise s.ValidationError({'detail': 'Dates invalides.'})
        if requis and not (debut and fin):
            raise s.ValidationError({'detail': 'date_debut et date_fin sont requis.'})
        if debut and fin and debut > fin:
            raise s.ValidationError({'detail': 'La date de début doit précéder la date de fin.'})
        return debut, fin

    def _prises_analyse(self, debut, fin):
        """Prises de la période, filtrées par agence, véhicule, chauffeur, type."""
        q = self.request.query_params
        qs = self.get_queryset().select_related('vehicule__agence', 'vehicule__marque', 'vehicule__modele')
        if debut: qs = qs.filter(date_plein__gte=debut)
        if fin:   qs = qs.filter(date_plein__lte=fin)
        if q.get('agence'):         qs = qs.filter(agence=q['agence'])
        if q.get('vehicule'):       qs = qs.filter(vehicule=q['vehicule'])
        if q.get('chauffeur'):      qs = qs.filter(chauffeur=q['chauffeur'])
        if q.get('type_mouvement'): qs = qs.filter(type_mouvement=q['type_mouvement'])
        return qs

    @action(detail=False, methods=['get'])
    def consommation(self, request):
        """
        Consommation par véhicule sur la période (méthode plein à plein) :
        km, litres, montant, conso moyenne vs consommation théorique de
        référence du véhicule, dernière conso, anomalies, part hors tournée.
        Paramètres : date_debut, date_fin (requis), agence, vehicule, chauffeur, type_mouvement.
        """
        debut, fin = self._periode()
        lignes = analyses.consommation_vehicules(list(self._prises_analyse(debut, fin)))
        return Response({'periode': {'debut': debut, 'fin': fin}, 'nb_vehicules': len(lignes), 'resultats': lignes})

    @action(detail=False, methods=['get'])
    def evolution_agences(self, request):
        """
        Évolution mensuelle par agence (mois vides à 0) : litres, montant,
        nombre de prises, km, conso, découpés tournées / hors tournée, et
        dotation théorique des tournées effectuées commencées dans le mois.
        Paramètres : date_debut, date_fin (requis), agence, vehicule, chauffeur, type_mouvement.
        """
        debut, fin = self._periode()
        q = request.query_params
        tes = filtrer_par_agence(TourneeEffectuee.objects.select_related('agence'), request.user) \
            .exclude(statut=TourneeEffectuee.Statut.ANNULEE).filter(date_debut__gte=debut, date_debut__lte=fin)
        if q.get('agence'):    tes = tes.filter(agence=q['agence'])
        if q.get('vehicule'):  tes = tes.filter(vehicule=q['vehicule'])
        if q.get('chauffeur'): tes = tes.filter(chauffeur=q['chauffeur'])
        if q.get('type_mouvement') and q['type_mouvement'] != TypeMouvement.CODE_TOURNEE:
            tes = tes.none()
        data = analyses.evolution_agences(list(self._prises_analyse(debut, fin)), list(tes), debut, fin)
        return Response({'periode': {'debut': debut, 'fin': fin}, **data})

    @action(detail=False, methods=['get'])
    def rapprochement_total(self, request):
        """
        Prises déclarées vs transactions TotalEnergies facturées sur la période :
        synthèse par véhicule (litres et montants), lignes rapprochées, écarts,
        transactions sans prise, prises sans transaction, plaques Total inconnues.
        Tolérances : Paramètres › Seuils (écart d'heure, écart de volume / montant).
        Paramètres : date_debut, date_fin (requis), agence, vehicule, chauffeur.
        """
        from apps.parametrage.models import Parametre
        from apps.total_import.models import TransactionCarburant
        from apps.vehicules.models import Vehicule
        debut, fin = self._periode()
        q = request.query_params
        prises = list(self._prises_analyse(debut, fin).select_related('station', 'chauffeur'))
        vehicules = filtrer_par_agence(Vehicule.objects.select_related('agence'), request.user, 'agence')
        if q.get('agence'):   vehicules = vehicules.filter(agence=q['agence'])
        if q.get('vehicule'): vehicules = vehicules.filter(pk=q['vehicule'])
        # Marge d'un jour : une transaction proche minuit peut répondre à une prise de la veille
        tx = filtrer_transactions_total(TransactionCarburant.objects.filter(
            date_transaction__gte=debut - timedelta(days=1), date_transaction__lte=fin + timedelta(days=1)),
            request.user)
        if q.get('chauffeur'):
            from apps.chauffeurs.models import Chauffeur
            c = Chauffeur.objects.filter(pk=q['chauffeur']).first()
            tx = tx.filter(numero_chauffeur=c.numero_chauffeur_total) if c and c.numero_chauffeur_total else tx.none()
        tolerance = float(Parametre.get(analyses.CLE_TOLERANCE_HEURES, analyses.TOLERANCE_HEURES_DEFAUT))
        ecart = float(Parametre.get(analyses.CLE_ECART_PCT, analyses.ECART_PCT_DEFAUT))
        data = analyses.rapprocher(prises, list(tx), list(vehicules), tolerance, ecart, periode=(debut, fin))
        if q.get('vehicule') or q.get('agence'):
            data['immatriculations_inconnues'] = []
        return Response({'periode': {'debut': debut, 'fin': fin}, **data})

class DotationViewSet(AgenceMixin, viewsets.ModelViewSet):
    serializer_class = DotationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['vehicule', 'mois', 'annee']

    module   = 'carburant'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]

    champ_agence = 'vehicule__agence'

    def get_queryset(self):
        return self.filtrer_agence(DotationCarburant.objects.select_related('vehicule'))


class StationViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    relations_utilisation = [('pleins', 'plein(s)'), ('rapprochements', 'rapprochement(s)')]
    serializer_class = StationSerializer
    module   = 'carburant'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'ville']
    filterset_fields = ['agence', 'est_partenaire', 'is_active']

    def get_queryset(self):
        # Stations de son agence et stations communes (sans agence) ;
        # listes : actives seulement, sauf ?tous=1 (page Paramètres)
        qs = annoter_utilisations(Station.objects.select_related('agence'), 'pleins')
        if self.action == 'list' and not self.request.query_params.get('tous'):
            qs = qs.filter(is_active=True)
        user = self.request.user
        if not voit_toutes_agences(user):
            qs = qs.filter(Q(agence__isnull=True) | Q(agence_id=user.agence_id))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(agence=agence_pour_creation(user, serializer.validated_data.get('agence')))

    def _verifier_station_modifiable(self, station):
        # Une station commune n'est modifiable que par « Toutes les agences »
        if station.agence_id is None and not voit_toutes_agences(self.request.user):
            raise PermissionDenied("Station commune : modification réservée aux utilisateurs « Toutes les agences ».")

    def perform_update(self, serializer):
        self._verifier_station_modifiable(serializer.instance)
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    def perform_destroy(self, instance):
        self._verifier_station_modifiable(instance)
        instance.delete()


class RapprochementViewSet(AgenceMixin, viewsets.ModelViewSet):
    serializer_class = RapprochementSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['agence', 'station', 'mois', 'annee', 'statut']

    module   = 'carburant'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]

    agence_a_la_creation = True

    def get_queryset(self):
        return self.filtrer_agence(RapprochementCarburant.objects.select_related('agence', 'station'))


class PrixCarburantViewSet(viewsets.ModelViewSet):
    """Historique des prix du carburant.

    GET  /carburant/prix/?type_carburant=diesel        — historique
    GET  /carburant/prix/en_vigueur/?type_carburant=&date=  (ou ?vehicule=<id>&date=)
    Un prix déjà entré en vigueur ne se modifie pas et ne se supprime pas :
    on ajoute un nouveau prix avec sa date d'effet.
    """
    serializer_class = PrixCarburantSerializer
    pagination_class = None
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['type_carburant']
    module   = 'carburant'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'en_vigueur': 'chauffeur',
        'create': 'responsable_flotte',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'responsable_flotte',
    }
    permission_classes = [RoleBasedPermission]

    def get_queryset(self):
        return PrixCarburant.objects.select_related('created_by')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _verifier_futur(self, prix):
        if prix.date_effet <= timezone.now().date():
            raise PermissionDenied(
                "Ce prix est déjà entré en vigueur : il fait partie de l'historique. "
                "Ajoutez un nouveau prix avec sa date d'effet.")

    def perform_update(self, serializer):
        self._verifier_futur(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._verifier_futur(instance)
        instance.delete()

    @action(detail=False, methods=['get'])
    def en_vigueur(self, request):
        from apps.vehicules.models import Vehicule
        date = request.query_params.get('date') or timezone.now().date().isoformat()
        type_carburant = request.query_params.get('type_carburant')
        vehicule_id = request.query_params.get('vehicule')
        if vehicule_id:
            vehicule = filtrer_par_agence(Vehicule.objects.all(), request.user).filter(pk=vehicule_id).first()
            if not vehicule:
                return Response({'detail': 'Véhicule introuvable.'}, status=404)
            type_carburant = vehicule.type_carburant
        if not type_carburant:
            return Response({'detail': 'type_carburant ou vehicule requis.'}, status=400)
        prix = PrixCarburant.en_vigueur(type_carburant, date)
        return Response({
            'type_carburant': type_carburant,
            'date': date,
            'prix': prix.prix if prix else None,
            'date_effet': prix.date_effet if prix else None,
        })


class TourneeEffectueeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Tournées effectuées et suivi carburant.
    GET  /carburant/tournees/                — suivi : une ligne par tournée effectuée
    GET  /carburant/tournees/hors_tournee/   — suivi des prises hors tournée
    GET  /carburant/tournees/synthese/       — tournées vs hors tournée
    GET  /carburant/tournees/en_cours/?vehicule=  — tournée en cours d'un véhicule
    POST /carburant/tournees/{id}/cloturer/  — {km_retour, date_fin, heure_fin, commentaire}
    POST /carburant/tournees/{id}/rouvrir/
    POST /carburant/tournees/{id}/annuler/   — {type_mouvement, motif}
    Filtres : date_debut, date_fin, agence, vehicule, immatriculation, tournee, statut, type_mouvement.
    """
    module = 'carburant'
    role_map = {'list': 'operateur', 'retrieve': 'operateur', 'hors_tournee': 'operateur',
                'synthese': 'operateur', 'en_cours': 'operateur', **tournees.DROITS_PAR_DEFAUT,
                'cloturer': 'operateur', 'rouvrir': 'responsable_flotte', 'annuler': 'responsable_flotte'}
    permission_actions = {'cloturer': tournees.ACTION_CLOTURER, 'rouvrir': tournees.ACTION_ROUVRIR,
                          'annuler': tournees.ACTION_ANNULER}
    pagination_class = None

    def get_permissions(self):
        return [RoleBasedPermission()]

    def get_queryset(self):
        qs = TourneeEffectuee.objects.select_related('vehicule', 'tournee', 'chauffeur', 'agence') \
            .prefetch_related(Prefetch('prises', queryset=PleinsCarburant.objects.select_related('station')))
        return filtrer_par_agence(qs, self.request.user)

    def _filtrer(self, qs, champ_date, champ_vehicule='vehicule'):
        q = self.request.query_params
        if q.get('date_debut'):      qs = qs.filter(**{f'{champ_date}__gte': q['date_debut']})
        if q.get('date_fin'):        qs = qs.filter(**{f'{champ_date}__lte': q['date_fin']})
        if q.get('agence'):          qs = qs.filter(agence=q['agence'])
        if q.get('vehicule'):        qs = qs.filter(**{champ_vehicule: q['vehicule']})
        if q.get('immatriculation'): qs = qs.filter(vehicule__immatriculation__icontains=q['immatriculation'])
        return qs

    def _tournees(self):
        q = self.request.query_params
        qs = self._filtrer(self.get_queryset(), 'date_debut')
        if q.get('tournee'): qs = qs.filter(tournee=q['tournee'])
        if q.get('statut'):  qs = qs.filter(statut=q['statut'])
        else:                qs = qs.exclude(statut=TourneeEffectuee.Statut.ANNULEE)
        cache = {}
        return [suivi.ligne_tournee(te, cache) for te in qs.order_by('date_debut', 'heure_debut')]

    def _hors_tournee(self):
        q = self.request.query_params
        qs = filtrer_par_agence(
            PleinsCarburant.objects.exclude(type_mouvement=TypeMouvement.CODE_TOURNEE)
            .select_related('vehicule', 'chauffeur', 'agence'), self.request.user)
        qs = self._filtrer(qs, 'date_plein')
        if q.get('type_mouvement'): qs = qs.filter(type_mouvement=q['type_mouvement'])
        types = {t.code: t for t in TypeMouvement.objects.all()}
        cache = {}
        return [suivi.ligne_hors_tournee(p, types, cache)
                for p in qs.order_by('date_plein', 'heure_plein', 'created_at')]

    def list(self, request, *args, **kwargs):
        lignes = self._tournees()
        return Response({'count': len(lignes), 'resultats': lignes, 'droits': tournees.droits(request.user)})

    def retrieve(self, request, *args, **kwargs):
        return Response({**suivi.ligne_tournee(self.get_object(), {}), 'droits': tournees.droits(request.user)})

    @action(detail=False, methods=['get'])
    def hors_tournee(self, request):
        lignes = self._hors_tournee()
        return Response({'count': len(lignes), 'resultats': lignes})

    @action(detail=False, methods=['get'])
    def synthese(self, request):
        return Response(suivi.synthese(self._tournees(), self._hors_tournee()))

    @action(detail=False, methods=['get'])
    def en_cours(self, request):
        from apps.vehicules.models import Vehicule
        vehicule = filtrer_par_agence(Vehicule.objects.all(), request.user) \
            .filter(pk=request.query_params.get('vehicule')).first() if request.query_params.get('vehicule') else None
        te = tournees.en_cours(vehicule)
        if te:
            te = self.get_queryset().get(pk=te.pk)
        return Response({'tournee': suivi.ligne_tournee(te, {}) if te else None,
                         'droits': tournees.droits(request.user)})

    def _date(self, champ):
        from rest_framework import serializers as s
        v = self.request.data.get(champ)
        if not v:
            return None
        f = s.DateField() if champ == 'date_fin' else s.TimeField()
        try:
            return f.to_internal_value(v)
        except s.ValidationError as e:
            raise s.ValidationError({champ: e.detail})

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        te = self.get_object()
        tournees.cloturer(te, request.user, km_retour=request.data.get('km_retour'),
                          date_fin=self._date('date_fin'), heure_fin=self._date('heure_fin'),
                          commentaire=(request.data.get('commentaire') or '').strip())
        return Response(suivi.ligne_tournee(self.get_queryset().get(pk=te.pk), {}))

    @action(detail=True, methods=['post'])
    def rouvrir(self, request, pk=None):
        te = tournees.rouvrir(self.get_object(), request.user)
        return Response(suivi.ligne_tournee(self.get_queryset().get(pk=te.pk), {}))

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        te = self.get_object()
        tournees.annuler(te, request.user, request.data.get('type_mouvement'), request.data.get('motif'))
        return Response({'detail': f"Tournée n° {te.numero} annulée."})

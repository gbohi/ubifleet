"""UbiFleet — Carburant Views"""

from datetime import time as datetime_time
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
from . import suivi, tournees
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

    @action(detail=False, methods=['get'])
    def consommation(self, request):
        """
        Rapport consommation L/100km par véhicule entre deux dates.
        Paramètres : date_debut, date_fin, immatriculation (optionnel), chauffeur (optionnel)
        Si date_debut/date_fin absents, retourne la moyenne globale (comportement historique).
        """
        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        immat      = request.query_params.get('immatriculation', '').strip()
        chauffeur  = request.query_params.get('chauffeur', '').strip()

        qs = self.get_queryset()
        if date_debut: qs = qs.filter(date_plein__gte=date_debut)
        if date_fin:   qs = qs.filter(date_plein__lte=date_fin)
        if immat:      qs = qs.filter(vehicule__immatriculation__icontains=immat)
        if chauffeur:  qs = qs.filter(chauffeur__nom__icontains=chauffeur)

        if not date_debut and not date_fin:
            # Comportement historique : moyenne de consommation_calculee
            qs2 = qs.filter(consommation_calculee__isnull=False).values(
                'vehicule__id', 'vehicule__immatriculation',
                'vehicule__marque', 'vehicule__modele', 'agence__nom'
            ).annotate(
                conso_moy=Avg('consommation_calculee'),
                total_litres=Sum('volume_litres'),
                total_montant=Sum('montant_fcfa'),
                nb_pleins=Count('id')
            ).order_by('-conso_moy')
            return Response({'resultats': list(qs2)})

        # Calcul : dernier plein de la période vs son prédécesseur immédiat
        # (même logique que la détection d'anomalie sur un plein individuel)
        resultats = []
        # IMPORTANT : Meta.ordering du modèle (-date_plein, -created_at) casse
        # le distinct() s'il n'est pas neutralisé — Django inclut ces colonnes
        # dans le DISTINCT SQL, ce qui produit une ligne par (véhicule, date, created_at)
        # au lieu d'une ligne par véhicule. On force order_by() vide ici.
        vehicule_ids = qs.order_by().values_list('vehicule__id', flat=True).distinct()

        for veh_id in vehicule_ids:
            dernier = (
                qs.filter(vehicule__id=veh_id)
                  .order_by('date_plein', 'heure_plein')
                  .last()
            )
            if not dernier:
                continue

            # Prédécesseur immédiat du dernier plein, sur TOUT l'historique
            # du véhicule (pas seulement dans la période filtrée), pour avoir
            # un point de comparaison même si la période ne contient qu'un plein.
            from django.db.models import Q
            heure_dernier = dernier.heure_plein or datetime_time.min
            predecesseur = (
                self.get_queryset()
                    .filter(vehicule__id=veh_id)
                    .filter(
                        Q(date_plein__lt=dernier.date_plein) |
                        Q(date_plein=dernier.date_plein, heure_plein__lt=heure_dernier)
                    )
                    .exclude(pk=dernier.pk)
                    .order_by('-date_plein', '-heure_plein')
                    .first()
            )
            if not predecesseur:
                continue

            km_debut = float(predecesseur.kilometrage_releve or 0)
            km_fin   = float(dernier.kilometrage_releve or 0)
            km_parcourus = km_fin - km_debut if km_fin > km_debut else 0

            volume  = float(dernier.volume_litres or 0)
            montant = float(dernier.montant_fcfa or 0)

            conso_100 = round((volume / km_parcourus) * 100, 2) if km_parcourus > 0 else None

            resultats.append({
                'immatriculation': dernier.vehicule.immatriculation,
                'marque':          dernier.vehicule.marque_str,
                'modele':          dernier.vehicule.modele_str,
                'km_debut':        km_debut,
                'km_fin':          km_fin,
                'km_parcourus':    round(km_parcourus, 0),
                'volume_total':    round(volume, 2),
                'montant_total':   round(montant, 2),
                'nb_pleins':       2,
                'conso_100':       conso_100,
                'premier_date':    predecesseur.date_plein,
                'premier_heure':   predecesseur.heure_plein,
                'dernier_date':    dernier.date_plein,
                'dernier_heure':   dernier.heure_plein,
            })

        resultats.sort(key=lambda x: x['conso_100'] or 0, reverse=True)
        return Response({
            'periode':   {'debut': date_debut, 'fin': date_fin},
            'nb_vehicules': len(resultats),
            'resultats': resultats,
        })

    @action(detail=False, methods=['get'])
    def consommation_moyenne_periode(self, request):
        """
        Consommation L/100km MOYENNE sur toute la période sélectionnée
        (du tout premier au tout dernier plein de la fenêtre), par véhicule.
        Paramètres : date_debut, date_fin (requis), immatriculation (optionnel), chauffeur (optionnel)
        """
        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        immat      = request.query_params.get('immatriculation', '').strip()
        chauffeur  = request.query_params.get('chauffeur', '').strip()

        if not date_debut or not date_fin:
            return Response({'detail': 'date_debut et date_fin sont requis.'}, status=400)

        qs = self.get_queryset().filter(
            date_plein__gte=date_debut,
            date_plein__lte=date_fin,
        )
        if immat:     qs = qs.filter(vehicule__immatriculation__icontains=immat)
        if chauffeur: qs = qs.filter(chauffeur__nom__icontains=chauffeur)

        resultats = []
        vehicule_ids = qs.order_by().values_list('vehicule__id', flat=True).distinct()

        for veh_id in vehicule_ids:
            pleins_vehicule = list(
                qs.filter(vehicule__id=veh_id).order_by('date_plein', 'heure_plein')
            )
            if len(pleins_vehicule) < 2:
                continue

            premier = pleins_vehicule[0]
            dernier = pleins_vehicule[-1]

            km_debut = float(premier.kilometrage_releve or 0)
            km_fin   = float(dernier.kilometrage_releve or 0)
            km_parcourus = km_fin - km_debut if km_fin > km_debut else 0

            # Volume consommé pour parcourir ces km : on exclut le 1er plein,
            # qui ne sert que de référence kilométrique de départ.
            volume = float(sum(p.volume_litres for p in pleins_vehicule[1:]))
            montant = float(sum(p.montant_fcfa for p in pleins_vehicule[1:]))
            nb_pleins = len(pleins_vehicule)

            conso_100 = round((volume / km_parcourus) * 100, 2) if km_parcourus > 0 else None

            resultats.append({
                'immatriculation': premier.vehicule.immatriculation,
                'marque':          premier.vehicule.marque_str,
                'modele':          premier.vehicule.modele_str,
                'km_debut':        km_debut,
                'km_fin':          km_fin,
                'km_parcourus':    round(km_parcourus, 0),
                'volume_total':    round(volume, 2),
                'montant_total':   round(montant, 2),
                'nb_pleins':       nb_pleins,
                'conso_100':       conso_100,
                'premier_date':    premier.date_plein,
                'premier_heure':   premier.heure_plein,
                'dernier_date':    dernier.date_plein,
                'dernier_heure':   dernier.heure_plein,
            })

        resultats.sort(key=lambda x: x['conso_100'] or 0, reverse=True)
        return Response({
            'periode':   {'debut': date_debut, 'fin': date_fin},
            'nb_vehicules': len(resultats),
            'resultats': resultats,
        })

    @action(detail=False, methods=['get'])
    def evolution_agences(self, request):
        """
        Évolution des prises de carburant UbiFleet par agence entre deux dates.
        Paramètres : date_debut, date_fin, immatriculation (optionnel), chauffeur (optionnel)
        """
        from django.db.models.functions import TruncMonth

        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        immat      = request.query_params.get('immatriculation', '').strip()
        chauffeur  = request.query_params.get('chauffeur', '').strip()

        if not date_debut or not date_fin:
            return Response({'detail': 'date_debut et date_fin sont requis.'}, status=400)

        qs = self.get_queryset().filter(
            date_plein__gte=date_debut,
            date_plein__lte=date_fin,
        )
        if immat:     qs = qs.filter(vehicule__immatriculation__icontains=immat)
        if chauffeur: qs = qs.filter(chauffeur__nom__icontains=chauffeur)

        series = (
            qs.annotate(mois=TruncMonth('date_plein'))
              .values('agence__id', 'agence__nom', 'mois')
              .annotate(
                  volume=Sum('volume_litres'),
                  montant=Sum('montant_fcfa'),
                  nb=Count('id'),
              )
              .order_by('agence__nom', 'mois')
        )

        agences_data: dict = {}
        for row in series:
            nom = row['agence__nom'] or 'Sans agence'
            mois_str = row['mois'].strftime('%Y-%m') if row['mois'] else '?'
            if nom not in agences_data:
                agences_data[nom] = {'nom': nom, 'points': []}
            agences_data[nom]['points'].append({
                'mois':    mois_str,
                'volume':  float(row['volume'] or 0),
                'montant': float(row['montant'] or 0),
                'nb':      row['nb'],
            })

        return Response({
            'periode': {'debut': date_debut, 'fin': date_fin},
            'agences': list(agences_data.values()),
        })

    @action(detail=False, methods=['get'])
    def comparaison_total(self, request):
        """
        Compare la consommation L/100km calculée côté UbiFleet (pleins déclarés)
        avec celle calculée côté Total (transactions facturées par la station),
        sur la même période et pour les mêmes véhicules.

        Paramètres : date_debut, date_fin, immatriculation (optionnel)

        Logique : pour chaque immatriculation présente d'un côté ou de l'autre,
        on calcule (volume total / km parcourus) * 100 sur la période, puis on
        compare les deux valeurs pour faire ressortir les écarts.
        """
        from django.db.models import Min, Max
        from apps.total_import.models import TransactionCarburant

        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        immat      = request.query_params.get('immatriculation', '').strip()

        if not date_debut or not date_fin:
            return Response({'detail': 'date_debut et date_fin sont requis.'}, status=400)

        # ── Côté UbiFleet ────────────────────────────────────────────
        qs_ubi = self.get_queryset().filter(
            date_plein__gte=date_debut,
            date_plein__lte=date_fin,
        )
        if immat:
            qs_ubi = qs_ubi.filter(vehicule__immatriculation__icontains=immat)

        ubi_par_vehicule: dict = {}
        immats_ubi = qs_ubi.order_by().values_list('vehicule__immatriculation', flat=True).distinct()

        for immat_veh in immats_ubi:
            cle = str(immat_veh or '').upper().strip()
            if not cle:
                continue

            pleins_veh = list(
                qs_ubi.filter(vehicule__immatriculation__iexact=cle)
                      .order_by('date_plein', 'heure_plein')
            )
            if len(pleins_veh) < 2:
                continue

            premier = pleins_veh[0]
            dernier = pleins_veh[-1]

            km_debut = float(premier.kilometrage_releve or 0)
            km_fin   = float(dernier.kilometrage_releve or 0)
            km_parcourus = km_fin - km_debut if km_fin > km_debut else 0

            # Volume hors 1er plein (référence kilométrique de départ seulement)
            volume  = float(sum(p.volume_litres for p in pleins_veh[1:]))
            montant = float(sum(p.montant_fcfa for p in pleins_veh[1:]))
            conso   = round((volume / km_parcourus) * 100, 2) if km_parcourus > 0 else None

            ubi_par_vehicule[cle] = {
                'volume':         round(volume, 2),
                'montant':        round(montant, 2),
                'nb_pleins':      len(pleins_veh),
                'km_debut':       km_debut,
                'km_fin':         km_fin,
                'km_parcourus':   round(km_parcourus, 0),
                'conso_100':      conso,
                'premier_date':   premier.date_plein,
                'premier_heure':  premier.heure_plein,
                'dernier_date':   dernier.date_plein,
                'dernier_heure':  dernier.heure_plein,
            }

        # ── Côté Total ───────────────────────────────────────────────
        qs_total = filtrer_transactions_total(TransactionCarburant.objects.filter(
            date_transaction__gte=date_debut,
            date_transaction__lte=date_fin,
        ).exclude(immatriculation='').exclude(immatriculation__isnull=True), request.user)
        if immat:
            qs_total = qs_total.filter(immatriculation__icontains=immat)

        total_par_vehicule: dict = {}
        for row in (
            qs_total.values('immatriculation')
                    .annotate(
                        volume_total = Sum('volume'),
                        montant_total= Sum('montant'),
                        nb_pleins    = Count('id'),
                        km_debut     = Min('kilometrage_precedent'),
                        km_fin       = Max('kilometrage_actuel'),
                    )
                    .filter(volume_total__gt=0)
        ):
            cle = str(row['immatriculation'] or '').upper().strip()
            if not cle:
                continue
            km_debut = float(row['km_debut'] or 0)
            km_fin   = float(row['km_fin'] or 0)
            km_parcourus = km_fin - km_debut if km_fin > km_debut else 0
            volume = float(row['volume_total'] or 0)
            conso  = round((volume / km_parcourus) * 100, 2) if km_parcourus > 0 else None

            trans_veh = qs_total.filter(
                immatriculation__iexact=cle
            ).order_by('date_transaction', 'heure_transaction')
            premiere = trans_veh.first()
            derniere = trans_veh.last()

            total_par_vehicule[cle] = {
                'volume':         round(volume, 2),
                'montant':        float(row['montant_total'] or 0),
                'nb_pleins':      row['nb_pleins'],
                'km_debut':       km_debut,
                'km_fin':         km_fin,
                'km_parcourus':   round(km_parcourus, 0),
                'conso_100':      conso,
                'premier_date':   premiere.date_transaction  if premiere else None,
                'premier_heure':  premiere.heure_transaction  if premiere else None,
                'dernier_date':   derniere.date_transaction  if derniere else None,
                'dernier_heure':  derniere.heure_transaction  if derniere else None,
            }

        # ── Rapprochement par immatriculation ───────────────────────
        toutes_immats = set(ubi_par_vehicule.keys()) | set(total_par_vehicule.keys())
        resultats = []
        for cle in sorted(toutes_immats):
            u = ubi_par_vehicule.get(cle)
            t = total_par_vehicule.get(cle)

            conso_ubi   = u['conso_100'] if u else None
            conso_total = t['conso_100'] if t else None

            ecart = None
            ecart_pct = None
            statut = 'donnees_insuffisantes'
            if conso_ubi is not None and conso_total is not None:
                ecart = round(conso_ubi - conso_total, 2)
                base  = conso_total if conso_total > 0 else conso_ubi
                ecart_pct = round((abs(ecart) / base) * 100, 1) if base else None
                if ecart_pct is not None and ecart_pct <= 10:
                    statut = 'coherent'
                elif ecart_pct is not None and ecart_pct <= 25:
                    statut = 'ecart_modere'
                else:
                    statut = 'ecart_important'
            elif u and not t:
                statut = 'total_absent'
            elif t and not u:
                statut = 'ubifleet_absent'

            resultats.append({
                'immatriculation':    cle,
                'ubifleet_volume':    u['volume']       if u else None,
                'ubifleet_km':        u['km_parcourus'] if u else None,
                'ubifleet_nb_pleins': u['nb_pleins']    if u else None,
                'ubifleet_conso_100': conso_ubi,
                'ubifleet_premier_date':  u['premier_date']  if u else None,
                'ubifleet_premier_heure': u['premier_heure'] if u else None,
                'ubifleet_dernier_date':  u['dernier_date']  if u else None,
                'ubifleet_dernier_heure': u['dernier_heure'] if u else None,
                'total_volume':       t['volume']       if t else None,
                'total_km':           t['km_parcourus'] if t else None,
                'total_nb_pleins':    t['nb_pleins']     if t else None,
                'total_conso_100':    conso_total,
                'total_premier_date':  t['premier_date']  if t else None,
                'total_premier_heure': t['premier_heure'] if t else None,
                'total_dernier_date':  t['dernier_date']  if t else None,
                'total_dernier_heure': t['dernier_heure'] if t else None,
                'ecart_conso':        ecart,
                'ecart_pct':          ecart_pct,
                'statut':             statut,
            })

        # Trier : écarts importants en premier
        ordre_statut = {'ecart_important': 0, 'ecart_modere': 1, 'ubifleet_absent': 2,
                         'total_absent': 3, 'coherent': 4, 'donnees_insuffisantes': 5}
        resultats.sort(key=lambda r: (ordre_statut.get(r['statut'], 9), -(r['ecart_pct'] or 0)))

        stats = {
            'total':            len(resultats),
            'coherent':         sum(1 for r in resultats if r['statut'] == 'coherent'),
            'ecart_modere':     sum(1 for r in resultats if r['statut'] == 'ecart_modere'),
            'ecart_important':  sum(1 for r in resultats if r['statut'] == 'ecart_important'),
            'ubifleet_absent':  sum(1 for r in resultats if r['statut'] == 'ubifleet_absent'),
            'total_absent':     sum(1 for r in resultats if r['statut'] == 'total_absent'),
        }

        return Response({
            'periode':   {'debut': date_debut, 'fin': date_fin},
            'stats':     stats,
            'resultats': resultats,
        })


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

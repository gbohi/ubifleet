"""UbiFleet — Véhicules Views"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters import rest_framework as df
from datetime import date, timedelta

from django.shortcuts import get_object_or_404

from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q

from .models import Vehicule, DocumentVehicule, TypeDocumentVehicule, ReleveKilometrage, HistoriqueImmatriculation, AffectationVehicule
from .serializers import (
    VehiculeListSerializer, VehiculeDetailSerializer,
    VehiculeWriteSerializer, DocumentVehiculeSerializer,
    ReleveKilometrageSerializer, HistoriqueImmatriculationSerializer,
    AffectationVehiculeSerializer,
    TypeDocumentVehiculeSerializer,
)
from apps.accounts.permissions import IsFleetManager, IsAgenceUser, RoleBasedPermission
from apps.parametrage.corrections import SaisieCorrigeableMixin
from apps.parametrage.fenetre_saisie import ACTION_HORS_DELAI, RELEVES, fenetre, tracer_hors_delai
from apps.vehicules.kilometrage import recalculer_kilometrage, heure_par_defaut
from apps.core.agences import (
    agence_effective, agence_pour_creation, controler_agence,
    filtrer_par_agence, filtrer_transactions_total,
)


class VehiculeFilter(FilterSet):
    agence = df.UUIDFilter(field_name='agence')
    statut = df.CharFilter(field_name='statut__code', lookup_expr='exact')
    type_carburant = df.ChoiceFilter(choices=Vehicule.TypeCarburant.choices)
    type_vehicule = df.ChoiceFilter(choices=Vehicule.TypeVehicule.choices)
    annee_min = df.NumberFilter(field_name='annee', lookup_expr='gte')
    annee_max = df.NumberFilter(field_name='annee', lookup_expr='lte')
    revision_due = df.BooleanFilter(method='filter_revision_due')

    class Meta:
        model = Vehicule
        fields = ['agence', 'statut', 'type_carburant', 'type_vehicule', 'is_active']

    def filter_revision_due(self, queryset, name, value):
        if value:
            return queryset.filter(
                kilometrage_revision__gt=0,
                kilometrage_actuel__gte=F('kilometrage_revision')
            )
        return queryset


class VehiculeViewSet(viewsets.ModelViewSet):
    """
    CRUD complet des véhicules.
    GET    /vehicules/           — liste paginée
    POST   /vehicules/           — créer
    GET    /vehicules/{id}/      — détail
    PATCH  /vehicules/{id}/      — modifier
    DELETE /vehicules/{id}/      — supprimer (soft)
    POST   /vehicules/{id}/kilometrage/   — MAJ kilométrage
    GET    /vehicules/{id}/historique/    — historique coûts
    GET    /vehicules/stats/              — statistiques globales
    """
    module   = 'vehicules'
    role_map = {
        'list': 'operateur', 'retrieve': 'operateur',
        'create': 'gestionnaire', 'update': 'gestionnaire',
        'partial_update': 'gestionnaire', 'destroy': 'responsable_flotte',
        'kilometrage': 'operateur', 'changer_immatriculation': 'responsable_flotte',
    }
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = VehiculeFilter
    search_fields = ['immatriculation', 'marque__libelle', 'modele__libelle', 'numero_chassis']
    ordering_fields = ['immatriculation', 'marque__libelle', 'annee', 'kilometrage_actuel', 'created_at']
    ordering = ['immatriculation']

    def get_permissions(self):
        return [RoleBasedPermission()]

    def get_queryset(self):
        qs = Vehicule.objects.select_related(
            'agence', 'chauffeur_attitré', 'created_by'
        ).filter(is_active=True)
        return filtrer_par_agence(qs, self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return VehiculeWriteSerializer
        if self.action == 'retrieve':
            return VehiculeDetailSerializer
        return VehiculeListSerializer

    def perform_create(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        km = serializer.validated_data.get('kilometrage_actuel', 0)
        serializer.save(created_by=user, kilometrage_initial=km,
                        agence=agence_pour_creation(user, serializer.validated_data.get('agence')))

    def perform_update(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        km_avant = serializer.instance.kilometrage_actuel
        vehicule = serializer.save()
        # Compteur relevé depuis la fiche : historisé, sinon perdu au prochain recalcul
        if vehicule.kilometrage_actuel > km_avant:
            ReleveKilometrage.objects.create(
                vehicule=vehicule, kilometrage=vehicule.kilometrage_actuel,
                date_releve=timezone.localdate(), heure_releve=heure_par_defaut(timezone.localdate()),
                type_mouvement='releve',
                notes='Kilométrage mis à jour depuis la fiche véhicule.', created_by=user,
            )

    def destroy(self, request, *args, **kwargs):
        """Soft delete."""
        vehicule = self.get_object()
        vehicule.is_active = False
        from apps.parametrage.models import StatutVehicule as SV
        statut_vendu = SV.objects.filter(code='vendu').first()
        if statut_vendu:
            vehicule.statut = statut_vendu
        vehicule.save()
        return Response({'detail': 'Véhicule archivé.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def kilometrage(self, request, pk=None):
        """Mise à jour du kilométrage + historisation du relevé."""
        vehicule = self.get_object()
        old_km = vehicule.kilometrage_actuel
        # Mêmes règles que la saisie d'un relevé (POST /vehicules/releves-km/)
        data = {k: v for k, v in request.data.items()}
        data['vehicule'] = str(vehicule.pk)
        data.setdefault('type_mouvement', 'releve')
        serializer = ReleveKilometrageSerializer(data=data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        controler_agence(request.user, serializer.validated_data)
        hors_delai = fenetre(request.user, RELEVES).controler_date(
            serializer.validated_data['date_releve'], 'date_releve')
        serializer.save(created_by=request.user, **(tracer_hors_delai(request.user) if hors_delai else {}))
        # Compteur recalculé à partir des saisies (un relevé antérieur ne le fait pas baisser)
        recalculer_kilometrage(vehicule)

        # Déclencher vérification alertes
        from apps.alertes.tasks import check_vehicule_alerts
        # Déclencher les alertes si Celery/Redis est disponible
        try:
            check_vehicule_alerts.delay(str(vehicule.id))
        except Exception:
            pass  # Redis non disponible — les alertes seront vérifiées au prochain cycle

        return Response({
            'detail': 'Kilométrage mis à jour.',
            'ancien': old_km,
            'nouveau': vehicule.kilometrage_actuel
        })

    @action(detail=True, methods=['post'])
    def changer_immatriculation(self, request, pk=None):
        """Remplace l'immatriculation de manière sécurisée avec historisation."""
        vehicule = self.get_object()

        nouvelle = request.data.get('nouvelle_immatriculation', '').strip().upper()
        date_changement = request.data.get('date_changement') or date.today()
        motif = request.data.get('motif', 'Passage de provisoire à définitive')

        if not nouvelle:
            return Response(
                {'detail': 'La nouvelle immatriculation est requise.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if nouvelle == vehicule.immatriculation:
            return Response(
                {'detail': 'La nouvelle immatriculation est identique.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Vehicule.objects.filter(immatriculation=nouvelle).exclude(pk=vehicule.pk).exists():
            return Response(
                {'detail': f"L'immatriculation {nouvelle} est deja utilisee."},
                status=status.HTTP_400_BAD_REQUEST
            )

        ancienne = vehicule.immatriculation
        HistoriqueImmatriculation.objects.create(
            vehicule=vehicule,
            ancienne_immatriculation=ancienne,
            nouvelle_immatriculation=nouvelle,
            date_changement=date_changement,
            motif=motif,
            created_by=request.user if request.user.is_authenticated else None,
        )
        vehicule.immatriculation_provisoire = ancienne
        vehicule.immatriculation = nouvelle
        vehicule.est_immatriculation_provisoire = False
        vehicule.date_immatriculation_definitive = date_changement
        vehicule.save()

        return Response({
            'detail': f'Immatriculation changee de {ancienne} vers {nouvelle}.',
            'ancienne': ancienne,
            'nouvelle': nouvelle,
        })

    @action(detail=True, methods=['get'])
    def historique_immatriculations(self, request, pk=None):
        """Historique des changements d'immatriculation du vehicule."""
        vehicule = self.get_object()
        qs = HistoriqueImmatriculation.objects.filter(vehicule=vehicule)
        serializer = HistoriqueImmatriculationSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """Historique complet des coûts du véhicule."""
        vehicule = self.get_object()
        from apps.carburant.models import PleinsCarburant
        from apps.entretien.models import Intervention
        from apps.sinistres.models import Sinistre

        data = {
            'vehicule': VehiculeListSerializer(vehicule).data,
            'nb_pleins': PleinsCarburant.objects.filter(vehicule=vehicule).count(),
            'cout_total_carburant': PleinsCarburant.objects.filter(
                vehicule=vehicule
            ).aggregate(total=Sum('montant_fcfa'))['total'] or 0,
            'nb_interventions': Intervention.objects.filter(vehicule=vehicule).count(),
            'cout_total_entretien': Intervention.objects.filter(
                vehicule=vehicule, statut='termine'
            ).aggregate(total=Sum('cout_reel'))['total'] or 0,
            'nb_sinistres': Sinistre.objects.filter(vehicule=vehicule).count(),
        }
        return Response(data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques globales du parc."""
        qs = self.get_queryset()
        data = {
            'total': qs.count(),
            'par_statut': {item['statut__code'] or 'inconnu': item['count'] for item in qs.values('statut__code').annotate(count=Count('id'))},
            'par_agence': list(
                qs.values('agence__nom', 'agence__code')
                  .annotate(count=Count('id'))
                  .order_by('agence__nom')
            ),
            'par_type': dict(qs.values_list('type_vehicule').annotate(count=Count('id'))),
            'revision_due': qs.filter(
                kilometrage_revision__gt=0,
                kilometrage_actuel__gte=F('kilometrage_revision')
            ).count(),
        }
        return Response(data)

    @action(detail=False, methods=['get'])
    def assurances_expirant(self, request):
        """Véhicules dont l'assurance expire dans les 30 prochains jours."""
        from django.utils import timezone
        import datetime
        threshold = timezone.now().date() + datetime.timedelta(days=30)

        vehicules = self.get_queryset().filter(
            documents__type_document='assurance',
            documents__date_expiration__lte=threshold,
            documents__date_expiration__gte=timezone.now().date()
        ).distinct()
        serializer = VehiculeListSerializer(vehicules, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=['get'])
    def etat_parc(self, request):
        """
        État complet du parc : un dict par véhicule avec km, documents,
        indicateurs de révision/pneus/documents.
        Paramètres (optionnels) : agence, type_vehicule, statut
        """
        from datetime import date as dt_date
        from apps.entretien.models import SuiviPneus
        from apps.vehicules.models import AffectationVehicule

        qs = self.get_queryset().filter(is_active=True).select_related(
            'agence'
        ).prefetch_related(
            'documents__type_document',
            'affectations__chauffeur',
        )

        agence   = request.query_params.get('agence')
        type_veh = request.query_params.get('type_vehicule')
        statut   = request.query_params.get('statut')
        if agence:   qs = qs.filter(agence__id=agence)
        if type_veh: qs = qs.filter(type_vehicule=type_veh)
        if statut:   qs = qs.filter(statut__code=statut)

        today = dt_date.today()
        resultats = []

        # ── Seuils des échéances (Paramètres › Échéances) ────────────
        from apps.parametrage.echeances import niveau, tous_les_seuils
        seuils = tous_les_seuils()

        def statut(code, restant):
            return niveau(restant, *seuils[code])

        # ── Pneus : une seule requête pour tous les véhicules ────────
        vehicule_ids = list(qs.values_list('id', flat=True))
        pneus_qs = SuiviPneus.objects.filter(
            vehicule_id__in=vehicule_ids,
            statut='en_service',
        ).exclude(kilometrage_remplacement__isnull=True)
        # Grouper par véhicule
        pneus_par_vehicule: dict = {}
        for p in pneus_qs:
            pneus_par_vehicule.setdefault(str(p.vehicule_id), []).append(p)

        for v in qs.order_by('immatriculation'):
            vid = str(v.id)

            # ── Chauffeur actif : affectation la plus récente
            # (date_fin nulle OU dans le futur), triée par date_debut DESC ──
            chauffeur_nom = None
            for aff in sorted(v.affectations.all(),
                               key=lambda a: a.date_debut, reverse=True):
                if aff.date_fin is None or aff.date_fin >= today:
                    c = aff.chauffeur
                    chauffeur_nom = f"{c.prenom} {c.nom}" if c else None
                    break

            # ── Km révision ──────────────────────────────────────────
            km_rev = v.kilometrage_revision or 0
            km_restant_rev = km_rev - v.kilometrage_actuel if km_rev > 0 else None

            # ── Pneus ────────────────────────────────────────────────
            pneus_v = pneus_par_vehicule.get(vid, [])
            km_pneu_min = None
            km_restant_pneu = None
            if pneus_v:
                km_pneu_min = min(p.kilometrage_remplacement for p in pneus_v)
                km_restant_pneu = km_pneu_min - v.kilometrage_actuel

            # ── Documents ────────────────────────────────────────────
            def jours_restants(code):
                docs = [
                    d for d in v.documents.all()
                    if d.type_document.code == code and d.date_expiration
                ]
                if not docs:
                    return None
                doc = max(docs, key=lambda d: d.date_expiration)
                return (doc.date_expiration - today).days

            jr_assurance     = jours_restants(TypeDocumentVehicule.CODE_ASSURANCE)
            jr_ct            = jours_restants(TypeDocumentVehicule.CODE_CT)
            jr_carte_transp  = jours_restants(TypeDocumentVehicule.CODE_CARTE_TRANSPORT)
            jr_vignette      = jours_restants(TypeDocumentVehicule.CODE_VIGNETTE)

            # ── Âge ──────────────────────────────────────────────────
            age_mois = None
            if v.date_mise_en_service:
                delta = today - v.date_mise_en_service
                age_mois = round(delta.days / 30.44, 1)

            resultats.append({
                'id':                  str(v.id),
                'immatriculation':     v.immatriculation,
                'marque':              v.marque_str,
                'modele':              v.modele_str,
                'annee':               v.annee,
                'type_vehicule':       v.get_type_vehicule_display(),
                'statut':              v.statut.code if v.statut else '',
                'statut_display':      v.statut.libelle if v.statut else '',
                'disponible':          bool(v.statut and v.statut.code == 'en_service'),
                'agence_nom':          v.agence.nom if v.agence else None,
                'chauffeur_nom':       chauffeur_nom,
                'kilometrage_actuel':  v.kilometrage_actuel,
                'km_prevu_revision':   km_rev or None,
                'km_restant_revision': km_restant_rev,
                'statut_revision':     statut('revision', km_restant_rev),
                'km_prevu_pneus':      km_pneu_min,
                'km_restant_pneus':    km_restant_pneu,
                'statut_pneus':        statut('pneus', km_restant_pneu),
                'jr_assurance':        jr_assurance,
                'statut_assurance':    statut('assurance', jr_assurance),
                'jr_ct':               jr_ct,
                'statut_ct':           statut('ct', jr_ct),
                'jr_carte_transport':  jr_carte_transp,
                'statut_carte_transport': statut('carte_transport', jr_carte_transp),
                'jr_vignette':         jr_vignette,
                'statut_vignette':     statut('vignette', jr_vignette),
                'age_mois':            age_mois,
                'notes':               v.notes or '',
            })

        # KPIs globaux
        def count_statut(lst, key, val):
            return sum(1 for r in lst if r.get(key) == val)

        kpis = {
            'total':                   len(resultats),
            'disponibles':             sum(1 for r in resultats if r['disponible']),
            'indisponibles':           sum(1 for r in resultats if not r['disponible']),
            'revision_urgente':        count_statut(resultats, 'statut_revision', 'urgent') +
                                       count_statut(resultats, 'statut_revision', 'depasse'),
            'revision_attention':      count_statut(resultats, 'statut_revision', 'attention'),
            'docs_expires':            sum(1 for r in resultats if any(
                                           r.get(f'statut_{k}') == 'depasse'
                                           for k in ['assurance','ct','carte_transport','vignette']
                                       )),
            'docs_urgents':            sum(1 for r in resultats if any(
                                           r.get(f'statut_{k}') == 'urgent'
                                           for k in ['assurance','ct','carte_transport','vignette']
                                       )),
            'pneus_urgents':           count_statut(resultats, 'statut_pneus', 'urgent') +
                                       count_statut(resultats, 'statut_pneus', 'depasse'),
        }

        return Response({
            'kpis':    kpis,
            'seuils':  {
                code: {'attention': att, 'urgent': urg}
                for code, (att, urg) in seuils.items()
            },
            'vehicules': resultats,
        })


class DocumentVehiculeViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentVehiculeSerializer
    module   = 'vehicules'
    role_map = {
            'list': 'operateur',
            'retrieve': 'operateur',
            'create': 'gestionnaire',
            'update': 'gestionnaire',
            'partial_update': 'gestionnaire',
            'destroy': 'responsable_flotte',
            'kilometrage': 'operateur',
            'changer_immatriculation': 'responsable_flotte',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]


    module   = 'vehicules'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
        'kilometrage': 'operateur',
        'changer_immatriculation': 'responsable_flotte',
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filtrer_par_agence(DocumentVehicule.objects.filter(
            vehicule__id=self.kwargs.get('vehicule_pk')
        ), self.request.user, 'vehicule__agence')

    def perform_create(self, serializer):
        vehicule = get_object_or_404(
            filtrer_par_agence(Vehicule.objects.all(), self.request.user),
            pk=self.kwargs['vehicule_pk'],
        )
        serializer.save(vehicule=vehicule, created_by=self.request.user)


class ReleveKilometrageViewSet(SaisieCorrigeableMixin, viewsets.ModelViewSet):
    """CRUD complet sur les relevés kilométrage."""
    from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
    serializer_class = ReleveKilometrageSerializer
    # Fenêtre de saisie et journal des corrections (cf. parametrage.corrections)
    domaine_saisie = RELEVES
    champ_date     = 'date_releve'
    champs_journal = ('vehicule', 'kilometrage', 'date_releve', 'heure_releve', 'type_mouvement', 'chauffeur',
                      'tournee', 'notes', 'photo_tableau_bord')
    parser_classes   = [MultiPartParser, FormParser, JSONParser]
    module   = 'releves_km'
    role_map = {
            'list': 'operateur',
            'retrieve': 'operateur',
            'create': 'operateur',
            'update': 'gestionnaire',
            'partial_update': 'gestionnaire',
            'destroy': 'responsable_flotte',
            ACTION_HORS_DELAI: 'responsable_flotte',   # droit complémentaire, cf. fenetre_saisie
    }

    def get_permissions(self):
        return [RoleBasedPermission()]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Plages de dates et de kilométrage (filtres de la liste globale des relevés)
    filterset_fields = {
        'vehicule': ['exact'], 'type_mouvement': ['exact'], 'chauffeur': ['exact'],
        'date_releve': ['exact', 'gte', 'lte'], 'kilometrage': ['gte', 'lte'],
    }
    search_fields    = ['vehicule__immatriculation', 'chauffeur__nom', 'chauffeur__prenom',
                        'tournee__code', 'tournee__libelle', 'notes']
    ordering_fields  = ['date_releve', 'heure_releve', 'kilometrage', 'created_at']

    def get_queryset(self):
        return filtrer_par_agence(ReleveKilometrage.objects.select_related(
            'vehicule', 'created_by', 'chauffeur', 'tournee', 'hors_delai_par'
        ), self.request.user, 'vehicule__agence')

    def perform_create(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        hors_delai = fenetre(user, RELEVES).controler_date(
            serializer.validated_data['date_releve'], 'date_releve')
        releve = serializer.save(created_by=user, **(tracer_hors_delai(user) if hors_delai else {}))
        recalculer_kilometrage(releve.vehicule)


class HistoriqueImmatriculationViewSet(viewsets.ReadOnlyModelViewSet):
    """Liste en lecture seule des changements d'immatriculation."""
    serializer_class = HistoriqueImmatriculationSerializer
    module   = 'vehicules'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['vehicule']
    ordering_fields  = ['date_changement', 'created_at']

    def get_queryset(self):
        return filtrer_par_agence(HistoriqueImmatriculation.objects.select_related(
            'vehicule', 'created_by'
        ), self.request.user, 'vehicule__agence')




class ConsommationKmView(viewsets.ViewSet):
    """
    Consommation facturée par véhicule (onglet Consommation des relevés km et
    page Restitution mensuelle) : litres facturés par TotalEnergies (ventes non
    annulées, rattachées par la carte carburant ou la plaque normalisée) ÷ km
    du compteur UbiFleet (relevés et prises) entre la 1re et la dernière
    transaction de la période, hors litres de la 1re (plein à plein).
    Comparée à la consommation déclarée (prises) et à la référence du véhicule.
    Paramètres : date_debut, date_fin (requis), agence, vehicule, chauffeur.
    """
    module             = 'vehicules'
    permission_classes = [RoleBasedPermission]
    role_map           = {'list': 'operateur'}

    def list(self, request):
        from datetime import datetime, time as dtime, timedelta
        from rest_framework import serializers as drf_s
        from apps.carburant.analyses import consommation_facturee
        from apps.carburant.models import PleinsCarburant
        from apps.total_import.models import TransactionCarburant

        q = request.query_params
        try:
            debut = drf_s.DateField().to_internal_value(q.get('date_debut') or '')
            fin = drf_s.DateField().to_internal_value(q.get('date_fin') or '')
        except drf_s.ValidationError:
            return Response({'detail': 'date_debut et date_fin sont requis.'}, status=400)
        if debut > fin:
            return Response({'detail': 'La date de début doit précéder la date de fin.'}, status=400)

        vehicules = filtrer_par_agence(Vehicule.objects.select_related('agence', 'marque', 'modele'), request.user)
        agence_id = agence_effective(request.user, (q.get('agence') or '').strip())
        if agence_id:
            vehicules = vehicules.filter(agence_id=agence_id)
        if q.get('vehicule'):
            vehicules = vehicules.filter(pk=q['vehicule'])
        vehicules = list(vehicules)
        ids = [v.pk for v in vehicules]

        # Compteur UbiFleet : relevés et prises, avec une marge autour de la période
        marge_debut, marge_fin = debut - timedelta(days=60), fin + timedelta(days=60)
        saisies = {}
        for vid, d, h, km in ReleveKilometrage.objects.filter(
                vehicule_id__in=ids, date_releve__range=(marge_debut, marge_fin)) \
                .values_list('vehicule_id', 'date_releve', 'heure_releve', 'kilometrage'):
            saisies.setdefault(vid, []).append((datetime.combine(d, h or dtime(12, 0)), km))
        for vid, d, h, km in PleinsCarburant.objects.filter(
                vehicule_id__in=ids, date_plein__range=(marge_debut, marge_fin)) \
                .values_list('vehicule_id', 'date_plein', 'heure_plein', 'kilometrage_releve'):
            saisies.setdefault(vid, []).append((datetime.combine(d, h or dtime(12, 0)), km))
        for liste in saisies.values():
            liste.sort()

        prises = PleinsCarburant.objects.filter(vehicule_id__in=ids, date_plein__range=(debut, fin)) \
            .select_related('vehicule__agence', 'vehicule__marque', 'vehicule__modele')
        tx = filtrer_transactions_total(TransactionCarburant.objects.filter(
            date_transaction__range=(debut, fin)), request.user)
        if q.get('chauffeur'):
            from apps.chauffeurs.models import Chauffeur
            c = Chauffeur.objects.filter(pk=q['chauffeur']).first()
            prises = prises.filter(chauffeur=c)
            tx = tx.filter(numero_chauffeur=c.numero_chauffeur_total) if c and c.numero_chauffeur_total else tx.none()

        data = consommation_facturee(vehicules, saisies, list(prises), list(tx), (debut, fin))
        if q.get('vehicule') or agence_id:
            data['immatriculations_inconnues'] = []
        return Response({'periode': {'debut': debut, 'fin': fin}, 'nb_vehicules': len(data['resultats']), **data})


class UtilisationParcView(viewsets.ViewSet):
    """
    Utilisation du parc (onglet des relevés kilométriques), cf. utilisation.py.
    GET /vehicules/utilisation/?date_debut=&date_fin=&agence=&vehicule=
    GET /vehicules/utilisation/courbe/?vehicule=&date_debut=&date_fin=  — saisies du compteur
    """
    module             = 'releves_km'
    permission_classes = [RoleBasedPermission]
    role_map           = {'list': 'operateur', 'courbe': 'operateur'}

    def _periode(self, request):
        from rest_framework import serializers as drf_s
        try:
            debut = drf_s.DateField().to_internal_value(request.query_params.get('date_debut') or '')
            fin = drf_s.DateField().to_internal_value(request.query_params.get('date_fin') or '')
        except drf_s.ValidationError:
            raise drf_s.ValidationError({'detail': 'date_debut et date_fin sont requis.'})
        if debut > fin:
            raise drf_s.ValidationError({'detail': 'La date de début doit précéder la date de fin.'})
        return debut, fin

    def _vehicules(self, request):
        q = request.query_params
        qs = filtrer_par_agence(Vehicule.objects.filter(is_active=True)
                                .select_related('agence', 'marque', 'modele', 'statut'), request.user)
        agence_id = agence_effective(request.user, (q.get('agence') or '').strip())
        if agence_id:
            qs = qs.filter(agence_id=agence_id)
        if q.get('vehicule'):
            qs = qs.filter(pk=q['vehicule'])
        return list(qs.order_by('immatriculation'))

    def list(self, request):
        from .utilisation import saisies_des_vehicules, utilisation
        debut, fin = self._periode(request)
        vehicules = self._vehicules(request)
        saisies = saisies_des_vehicules([v.pk for v in vehicules], fin + timedelta(days=60))
        return Response({'periode': {'debut': debut, 'fin': fin},
                         **utilisation(vehicules, saisies, debut, fin, timezone.localdate())})

    def courbe(self, request):
        from .utilisation import saisies_des_vehicules
        debut, fin = self._periode(request)
        vehicules = self._vehicules(request)
        if not request.query_params.get('vehicule') or not vehicules:
            return Response({'detail': 'Véhicule introuvable.'}, status=404)
        v = vehicules[0]
        points = [{'quand': q.isoformat(), 'km': km, 'source': src}
                  for q, km, src in saisies_des_vehicules([v.pk], fin).get(v.pk, []) if q.date() >= debut]
        return Response({'vehicule': v.immatriculation, 'points': points})


class TypeDocumentVehiculeViewSet(viewsets.ModelViewSet):
    """CRUD types de documents véhicule — géré depuis la page Paramètres."""
    serializer_class   = TypeDocumentVehiculeSerializer
    queryset           = TypeDocumentVehicule.objects.all()
    pagination_class   = None  # Liste complète, pas de pagination

    def perform_create(self, serializer):
        """Génère le code automatiquement depuis le libellé si absent."""
        import re, unicodedata
        libelle = serializer.validated_data.get('libelle', '')
        # Normaliser : minuscules, accents → ascii, espaces → _, ponctuation supprimée
        nfkd = unicodedata.normalize('NFKD', libelle)
        ascii_str = nfkd.encode('ascii', 'ignore').decode()
        code = re.sub(r'[^a-z0-9]+', '_', ascii_str.lower()).strip('_')
        # S'assurer de l'unicité
        base = code; i = 2
        while TypeDocumentVehicule.objects.filter(code=code).exists():
            code = f"{base}_{i}"; i += 1
        serializer.save(code=code)
    module           = 'vehicules'
    role_map         = {
        'list':           'operateur',
        'retrieve':       'operateur',
        'create':         'responsable_flotte',
        'update':         'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy':        'responsable_flotte',
    }
    permission_classes = [RoleBasedPermission]

    def get_queryset(self):
        qs = TypeDocumentVehicule.objects.all()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() == 'true')
        return qs

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.documents.exists():
            from rest_framework.response import Response
            return Response(
                {'detail': f'Impossible de supprimer : {obj.documents.count()} document(s) utilisent ce type.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class AffectationVehiculeViewSet(viewsets.ModelViewSet):
    """CRUD des affectations véhicule ↔ chauffeur."""
    serializer_class   = AffectationVehiculeSerializer
    module   = 'affectations'
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
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['vehicule', 'chauffeur', 'date_debut', 'date_fin']
    ordering_fields    = ['date_debut', 'created_at']

    def get_queryset(self):
        return filtrer_par_agence(AffectationVehicule.objects.select_related(
            'vehicule', 'chauffeur', 'created_by'
        ), self.request.user, 'vehicule__agence')

    def perform_create(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()


class HistoriqueStatutVehiculeViewSet(viewsets.ModelViewSet):
    """Historique des changements de statut d'un véhicule."""
    module             = 'vehicules'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'responsable_flotte',
    }
    pagination_class   = None

    def get_serializer_class(self):
        from .serializers import HistoriqueStatutVehiculeSerializer
        return HistoriqueStatutVehiculeSerializer

    def get_queryset(self):
        from .models import HistoriqueStatutVehicule
        qs = HistoriqueStatutVehicule.objects.select_related(
            'ancien_statut', 'nouveau_statut', 'vehicule', 'created_by'
        )
        vehicule_id = self.request.query_params.get('vehicule') or self.kwargs.get('vehicule_pk')
        if vehicule_id:
            qs = qs.filter(vehicule__id=vehicule_id)
        return filtrer_par_agence(qs, self.request.user, 'vehicule__agence')

    def perform_create(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

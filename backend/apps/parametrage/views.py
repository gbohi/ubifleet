"""UbiFleet — Paramétrage Views"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Parametre
from .serializers import ParametreSerializer
from apps.accounts.permissions import IsSuperAdmin, IsFleetManager, RoleBasedPermission
from apps.core.agences import controler_agence, filtrer_par_agence, voit_toutes_agences
from django.db.models import Count as _Count, IntegerField, OuterRef, Q, Subquery
from apps.core.referentiels import NbUtilisationsField, SuppressionProtegeeMixin, annoter_utilisations


class ReferentielPermissionMixin:
    """Référentiels du paramétrage : lecture pour tous les utilisateurs
    (listes déroulantes des formulaires), modification réservée au
    responsable flotte et plus."""
    module             = 'parametres'
    permission_classes = [RoleBasedPermission]
    role_map = {
        'list': 'chauffeur',
        'retrieve': 'chauffeur',
        'create': 'responsable_flotte',
        'update': 'responsable_flotte',
        'partial_update': 'responsable_flotte',
        'destroy': 'responsable_flotte',
        'import_excel': 'responsable_flotte',
    }


class ParametreViewSet(viewsets.ModelViewSet):
    queryset = Parametre.objects.all()
    module   = 'parametres'
    serializer_class = ParametreSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categorie']
    search_fields = ['cle', 'description']

    def get_permissions(self):
        # Lecture pour tous les authentifiés
        if self.action in ['list', 'retrieve', 'by_categorie']:
            return [IsAuthenticated()]
        # bulk_update pour les admins (niveau >= 6)
        if self.action == 'bulk_update':
            return [IsFleetManager()]
        return [IsSuperAdmin()]

    @action(detail=False, methods=['get'])
    def by_categorie(self, request):
        """Retourne les paramètres regroupés par catégorie."""
        result = {}
        for p in self.get_queryset():
            cat = p.get_categorie_display()
            if cat not in result:
                result[cat] = []
            result[cat].append(ParametreSerializer(p).data)
        return Response(result)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Mise à jour en masse : [{cle, valeur}, ...].

        Clés acceptées : paramètres existants et seuils connus (échéances,
        consommation). Pour chaque échéance, le seuil
        « attention » doit rester strictement supérieur au seuil « urgent »."""
        from .echeances import ECHEANCES, CLE_CONSO_ANOMALIE, cle, seuils
        from . import fenetre_saisie

        if not isinstance(request.data, list):
            return Response({'detail': 'Format invalide. Attendu: liste.'}, status=400)

        # Le prix du carburant a son propre historique daté (/carburant/prix/)
        CONNUES = {CLE_CONSO_ANOMALIE: 'alertes'}
        for code in ECHEANCES:
            CONNUES[cle(code, 'attention')] = 'alertes'
            CONNUES[cle(code, 'urgent')] = 'alertes'
        # Fenêtres de saisie : 0 = désactivée
        FENETRES = {fenetre_saisie.cle(d): 'carburant' if d == fenetre_saisie.CARBURANT else 'general'
                    for d in fenetre_saisie.DOMAINES}
        CONNUES.update(FENETRES)

        valeurs, erreurs = {}, []
        for item in request.data:
            k, v = item.get('cle'), item.get('valeur')
            if not k or v is None:
                continue
            if k in CONNUES:
                try:
                    v = int(float(v))
                except (TypeError, ValueError):
                    erreurs.append(f'« {k} » doit être un nombre.')
                    continue
                if k in FENETRES:
                    if not 0 <= v <= fenetre_saisie.JOURS_MAX:
                        erreurs.append(f'La fenêtre de saisie doit être comprise entre 1 et '
                                       f'{fenetre_saisie.JOURS_MAX} jours (0 pour la désactiver).')
                        continue
                elif v < 1:
                    erreurs.append(f'« {k} » doit être supérieur à 0.')
                    continue
            elif not Parametre.objects.filter(cle=k).exists():
                erreurs.append(f'Paramètre inconnu : « {k} ».')
                continue
            valeurs[k] = v

        # Cohérence attention > urgent (en tenant compte des valeurs non envoyées)
        for code, e in ECHEANCES.items():
            att_actuel, urg_actuel = seuils(code)
            att = valeurs.get(cle(code, 'attention'), att_actuel)
            urg = valeurs.get(cle(code, 'urgent'), urg_actuel)
            if att <= urg:
                erreurs.append(f'{e.libelle} : le seuil « attention » ({att} {e.unite}) doit être '
                               f'supérieur au seuil « urgent » ({urg} {e.unite}).')
        if erreurs:
            return Response({'detail': ' '.join(erreurs), 'erreurs': erreurs}, status=400)

        for k, v in valeurs.items():
            if k in CONNUES:
                Parametre.objects.update_or_create(cle=k, defaults={
                    'valeur': str(v), 'type_valeur': 'int', 'categorie': CONNUES[k],
                })
            else:
                p = Parametre.objects.get(cle=k)
                p.valeur = str(v)
                p.save(update_fields=['valeur', 'updated_at'])
        return Response({'updated': list(valeurs)})


class FenetreSaisieView(viewsets.ViewSet):
    """Fenêtres de saisie applicables à l'utilisateur connecté :
    {carburant: {jours, active, date_min, date_max, hors_delai}, releves: {...}}.
    date_max est la date du jour du serveur."""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        from . import fenetre_saisie as fs
        return Response({d: fs.fenetre(request.user, d).en_dict() for d in fs.DOMAINES})


from .models import Tournee, ChangementDotation
from rest_framework import serializers as drf_serializers


class TourneeSerializer(drf_serializers.ModelSerializer):
    agence_nom  = drf_serializers.CharField(source='agence.nom',  read_only=True)
    agence_code = drf_serializers.CharField(source='agence.code', read_only=True)
    # Nouvelle dotation demandée, en attente de validation (None sinon)
    dotation_en_attente = drf_serializers.IntegerField(read_only=True, default=None, allow_null=True)

    class Meta:
        model  = Tournee
        fields = ['id', 'code', 'libelle', 'agence', 'agence_nom', 'agence_code',
                  'dotation', 'dotation_en_attente', 'km_theorique', 'actif']

    def validate_dotation(self, value):
        # Fixée à la création ; ensuite, uniquement par demande validée
        if self.instance is not None and value != self.instance.dotation:
            raise drf_serializers.ValidationError(
                "La dotation se modifie par une demande soumise au circuit de validation "
                "(bouton « Demander une modification »).")
        return value


class ChangementDotationSerializer(drf_serializers.ModelSerializer):
    statut_display = drf_serializers.CharField(source='get_statut_display', read_only=True)
    demandeur_nom  = drf_serializers.CharField(source='demandeur.full_name', read_only=True, allow_null=True)
    decide_par_nom = drf_serializers.CharField(source='decide_par.full_name', read_only=True, allow_null=True)
    demande_numero = drf_serializers.CharField(source='demande.numero', read_only=True, allow_null=True)

    class Meta:
        model  = ChangementDotation
        fields = ['id', 'ancienne_dotation', 'nouvelle_dotation', 'motif', 'statut', 'statut_display',
                  'demandeur_nom', 'decide_par_nom', 'date_decision', 'demande', 'demande_numero',
                  'created_at']


from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


class TourneeViewSet(ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = TourneeSerializer
    pagination_class   = None
    role_map = {
        **ReferentielPermissionMixin.role_map,
        'demander_dotation':   'responsable_flotte',
        'historique_dotation': 'chauffeur',
    }

    def get_queryset(self):
        en_attente = ChangementDotation.objects.filter(
            tournee=OuterRef('pk'), statut=ChangementDotation.Statut.EN_ATTENTE
        ).values('nouvelle_dotation')[:1]
        qs = filtrer_par_agence(
            Tournee.objects.select_related('agence').annotate(dotation_en_attente=Subquery(en_attente)),
            self.request.user)
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        agence = self.request.query_params.get('agence')
        if agence:
            qs = qs.filter(agence__id=agence)
        return qs

    def perform_create(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        tournee = serializer.save()
        ChangementDotation.objects.create(
            tournee=tournee, nouvelle_dotation=tournee.dotation, statut=ChangementDotation.Statut.INITIALE,
            demandeur=self.request.user, motif='Création de la tournée')

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    @action(detail=True, methods=['post'])
    def demander_dotation(self, request, pk=None):
        """Soumet une nouvelle dotation au circuit de validation « dotation »."""
        from .dotations import demander_modification
        tournee = self.get_object()
        try:
            nouvelle = int(request.data.get('nouvelle_dotation'))
            if nouvelle < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'nouvelle_dotation': 'Nombre de litres invalide.'}, status=400)
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response({'motif': 'Le motif est obligatoire.'}, status=400)
        changement = demander_modification(tournee, nouvelle, motif, request.user)
        return Response(ChangementDotationSerializer(changement).data, status=201)

    @action(detail=True, methods=['get'])
    def historique_dotation(self, request, pk=None):
        tournee = self.get_object()
        qs = tournee.changements_dotation.select_related('demandeur', 'decide_par', 'demande')
        return Response(ChangementDotationSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'],
            parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request):
        """
        Import en masse de tournées depuis un fichier Excel (.xlsx) ou CSV.

        Colonnes attendues (1re ligne = en-têtes, insensible à la casse) :
          code | libelle | agence | dotation | km_theorique | actif

        - `agence` : code OU nom de l'agence (doit exister)
        - `actif`  : optionnel (oui/non, true/false, 1/0) — défaut: oui
        - Une tournée dont le `code` existe déjà est mise à jour.
        """
        import io
        from apps.accounts.models import Agence

        fichier = request.FILES.get('fichier')
        if not fichier:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)

        nom = (fichier.name or '').lower()
        contenu = fichier.read()

        # ── Lecture des lignes ────────────────────────────────────────
        lignes = []
        try:
            if nom.endswith('.csv'):
                import csv
                texte = contenu.decode('utf-8-sig', errors='replace')
                dialecte = csv.Sniffer().sniff(texte[:2000], delimiters=';,\t')
                for row in csv.reader(io.StringIO(texte), dialecte):
                    lignes.append(row)
            else:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(contenu),
                                            read_only=True, data_only=True)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    lignes.append(list(row))
                wb.close()
        except Exception as e:
            return Response({'detail': f'Fichier illisible : {e}'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Retirer les lignes totalement vides
        lignes = [l for l in lignes
                  if any(str(c).strip() for c in l if c is not None)]
        if len(lignes) < 2:
            return Response({'detail': 'Le fichier ne contient aucune donnée.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ── En-têtes ──────────────────────────────────────────────────
        entetes = [str(c or '').strip().lower() for c in lignes[0]]

        def idx(*noms):
            for n in noms:
                if n in entetes:
                    return entetes.index(n)
            return None

        i_code   = idx('code')
        i_lib    = idx('libelle', 'libellé', 'designation', 'désignation')
        i_agence = idx('agence', 'code_agence', 'agence_code')
        i_dot    = idx('dotation', 'dotation_l', 'dotation (l)')
        i_km     = idx('km_theorique', 'km theorique', 'km théorique', 'km')
        i_actif  = idx('actif', 'active')

        manquants = [nom_col for nom_col, i in
                     [('code', i_code), ('libelle', i_lib), ('agence', i_agence)]
                     if i is None]
        if manquants:
            return Response(
                {'detail': 'Colonnes obligatoires manquantes : ' + ', '.join(manquants)
                           + '. En-têtes attendus : code, libelle, agence, '
                             'dotation, km_theorique, actif.'},
                status=status.HTTP_400_BAD_REQUEST)

        # ── Index des agences (par code et par nom, insensible à la casse) ──
        agences = {}
        for a in filtrer_par_agence(Agence.objects.all(), request.user, 'pk'):
            agences[(a.code or '').strip().lower()] = a
            agences[(a.nom or '').strip().lower()]  = a

        def en_entier(val):
            if val is None or str(val).strip() == '':
                return 0
            try:
                return int(float(str(val).strip().replace(' ', '').replace(',', '.')))
            except (TypeError, ValueError):
                return 0

        def en_booleen(val):
            if val is None or str(val).strip() == '':
                return True
            return str(val).strip().lower() in ('1', 'oui', 'true', 'vrai', 'o', 'x', 'yes')

        crees, maj, erreurs = 0, 0, []

        for num, ligne in enumerate(lignes[1:], start=2):
            def cell(i):
                if i is None or i >= len(ligne) or ligne[i] is None:
                    return ''
                return str(ligne[i]).strip()

            code = cell(i_code)
            lib  = cell(i_lib)
            ag   = cell(i_agence)

            if not code:
                erreurs.append(f'Ligne {num} : code manquant.')
                continue
            if not lib:
                erreurs.append(f'Ligne {num} : libellé manquant.')
                continue

            agence = agences.get(ag.lower())
            if agence is None:
                erreurs.append(f'Ligne {num} : agence « {ag} » introuvable.')
                continue

            valeurs = {
                'libelle':      lib[:100],
                'agence':       agence,
                'dotation':     en_entier(cell(i_dot)),
                'km_theorique': en_entier(cell(i_km)),
                'actif':        en_booleen(cell(i_actif)),
            }

            existante = Tournee.objects.filter(code=code[:20]).first()
            if existante and not voit_toutes_agences(request.user) \
                    and existante.agence_id != request.user.agence_id:
                erreurs.append(f'Ligne {num} : la tournée « {code} » appartient à une autre agence.')
                continue

            if existante and existante.dotation != valeurs['dotation']:
                erreurs.append(
                    f"Ligne {num} : dotation de « {code} » non modifiée ({existante.dotation} L conservés) — "
                    "une modification de dotation passe par une demande validée.")
                valeurs['dotation'] = existante.dotation

            try:
                obj, cree = Tournee.objects.update_or_create(
                    code=code[:20], defaults=valeurs
                )
                if cree:
                    crees += 1
                    ChangementDotation.objects.create(
                        tournee=obj, nouvelle_dotation=obj.dotation, statut=ChangementDotation.Statut.INITIALE,
                        demandeur=request.user, motif='Création par import Excel')
                else:
                    maj += 1
            except Exception as e:
                erreurs.append(f'Ligne {num} : {e}')

        return Response({
            'crees':   crees,
            'maj':     maj,
            'erreurs': erreurs[:50],
            'nb_erreurs': len(erreurs),
            'detail': f'{crees} tournée(s) créée(s), {maj} mise(s) à jour.',
        })


from .models import AffectationUsage, StatutVehicule, MarqueVehicule, ModeleVehicule
from rest_framework import serializers as drf_s2


class AffectationUsageSerializer(drf_s2.ModelSerializer):
    class Meta:
        model  = AffectationUsage
        fields = ['id', 'code', 'libelle', 'actif', 'nb_utilisations']

    nb_utilisations = NbUtilisationsField()


class StatutVehiculeSerializer(drf_s2.ModelSerializer):
    class Meta:
        model  = StatutVehicule
        fields = ['id', 'code', 'libelle', 'couleur', 'actif', 'nb_utilisations']

    nb_utilisations = NbUtilisationsField()


class AffectationUsageViewSet(SuppressionProtegeeMixin, ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = AffectationUsageSerializer
    pagination_class   = None
    relations_utilisation = [('vehicules', 'véhicule(s)')]

    def get_queryset(self):
        qs = annoter_utilisations(AffectationUsage.objects.all(), 'vehicules', Q(vehicules__is_active=True))
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


class StatutVehiculeViewSet(SuppressionProtegeeMixin, ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = StatutVehiculeSerializer
    pagination_class   = None
    relations_utilisation = [('vehicules', 'véhicule(s)')]

    def get_queryset(self):
        qs = annoter_utilisations(StatutVehicule.objects.all(), 'vehicules', Q(vehicules__is_active=True))
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


class MarqueVehiculeSerializer(drf_s2.ModelSerializer):
    nb_modeles = drf_s2.SerializerMethodField()

    class Meta:
        model  = MarqueVehicule
        fields = ['id', 'libelle', 'actif', 'nb_modeles', 'nb_utilisations']

    nb_utilisations = NbUtilisationsField()

    def get_nb_modeles(self, obj):
        return obj.modeles.count()


class ModeleVehiculeSerializer(drf_s2.ModelSerializer):
    marque_libelle = drf_s2.CharField(source='marque.libelle', read_only=True)

    class Meta:
        model  = ModeleVehicule
        fields = ['id', 'marque', 'marque_libelle', 'libelle', 'actif', 'nb_utilisations']

    nb_utilisations = NbUtilisationsField()


class MarqueVehiculeViewSet(SuppressionProtegeeMixin, ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = MarqueVehiculeSerializer
    pagination_class   = None
    relations_utilisation = [('vehicules', 'véhicule(s)')]

    def get_queryset(self):
        qs = annoter_utilisations(MarqueVehicule.objects.all(), 'vehicules', Q(vehicules__is_active=True))
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


class ModeleVehiculeViewSet(SuppressionProtegeeMixin, ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = ModeleVehiculeSerializer
    pagination_class   = None
    relations_utilisation = [('vehicules', 'véhicule(s)')]

    def get_queryset(self):
        qs = annoter_utilisations(ModeleVehicule.objects.select_related('marque'), 'vehicules', Q(vehicules__is_active=True))
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        marque = self.request.query_params.get('marque')
        if marque:
            qs = qs.filter(marque__id=marque)
        return qs


# ── Types de mouvement (relevés kilométriques) ───────────────────────
from .models import TypeMouvement


class TypeMouvementSerializer(drf_s2.ModelSerializer):
    nb_utilisations = NbUtilisationsField()

    class Meta:
        model  = TypeMouvement
        fields = ['id', 'code', 'libelle', 'couleur', 'avec_tournee', 'ordre', 'actif', 'nb_utilisations']

    def validate_code(self, value):
        if self.instance and self.instance.code != value:
            raise drf_s2.ValidationError(
                "Le code ne peut pas être modifié : il est enregistré sur les relevés existants.")
        return value


def _releves_par_type():
    from apps.vehicules.models import ReleveKilometrage
    return (ReleveKilometrage.objects.filter(type_mouvement=OuterRef('code'))
            .order_by().values('type_mouvement').annotate(n=_Count('id')).values('n'))


class TypeMouvementViewSet(SuppressionProtegeeMixin, ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = TypeMouvementSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = TypeMouvement.objects.annotate(
            nb_utilisations=Subquery(_releves_par_type(), output_field=IntegerField()))
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs

    def utilisations(self, obj):
        from apps.vehicules.models import ReleveKilometrage
        return [(ReleveKilometrage.objects.filter(type_mouvement=obj.code).count(), 'relevé(s) kilométrique(s)')]


from .models import CorrectionSaisie


class CorrectionSaisieSerializer(drf_serializers.ModelSerializer):
    action_display = drf_serializers.CharField(source='get_action_display', read_only=True)
    auteur_nom     = drf_serializers.CharField(source='auteur.full_name', read_only=True, allow_null=True)
    vehicule_immat = drf_serializers.CharField(source='vehicule.immatriculation', read_only=True, allow_null=True)

    class Meta:
        model  = CorrectionSaisie
        fields = ['id', 'domaine', 'objet_id', 'libelle', 'vehicule', 'vehicule_immat', 'action',
                  'action_display', 'auteur', 'auteur_nom', 'date', 'hors_delai', 'motif', 'changements']


class CorrectionSaisieViewSet(viewsets.ReadOnlyModelViewSet):
    """Journal des corrections de pleins et de relevés (lecture seule).
    Filtres : domaine, objet (id de la saisie), vehicule.
    Chaque domaine n'est visible qu'avec le droit de consulter la saisie
    correspondante ; données cloisonnées par agence du véhicule."""
    serializer_class   = CorrectionSaisieSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from apps.accounts.permissions import action_autorisee
        from apps.carburant.views import PleinViewSet
        from apps.vehicules.views import ReleveKilometrageViewSet
        from .fenetre_saisie import CARBURANT, RELEVES
        user = self.request.user
        domaines = [d for d, vue in ((CARBURANT, PleinViewSet), (RELEVES, ReleveKilometrageViewSet))
                    if action_autorisee(user, vue, 'list')]
        qs = CorrectionSaisie.objects.filter(domaine__in=domaines).select_related('auteur', 'vehicule')
        qs = filtrer_par_agence(qs, user, 'vehicule__agence')
        p = self.request.query_params
        if p.get('domaine'):
            qs = qs.filter(domaine=p['domaine'])
        if p.get('objet'):
            import uuid
            try:
                qs = qs.filter(objet_id=uuid.UUID(p['objet']))
            except ValueError:
                return qs.none()
        if p.get('vehicule'):
            qs = qs.filter(vehicule_id=p['vehicule'])
        return qs

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
        """Mise à jour en masse : [{cle, valeur, categorie?, type_valeur?}, ...]"""
        if not isinstance(request.data, list):
            return Response({'detail': 'Format invalide. Attendu: liste.'}, status=400)

        # Mapping cle → catégorie par défaut pour les paramètres connus
        CATEGORIE_DEFAULTS = {
            'etat_parc_km_urgent':      'alertes',
            'etat_parc_km_attention':   'alertes',
            'etat_parc_jours_urgent':   'alertes',
            'etat_parc_jours_attention':'alertes',
            'alerte_permis_jours':      'alertes',
            'alerte_assurance_jours':   'alertes',
            'alerte_ct_jours':          'alertes',
            'alerte_conso_seuil_pct':   'alertes',
        }
        TYPE_DEFAULTS = {
            'etat_parc_km_urgent':      'int',
            'etat_parc_km_attention':   'int',
            'etat_parc_jours_urgent':   'int',
            'etat_parc_jours_attention':'int',
            'alerte_permis_jours':      'int',
            'alerte_assurance_jours':   'int',
            'alerte_ct_jours':          'int',
            'alerte_conso_seuil_pct':   'int',
        }

        updated = []
        for item in request.data:
            cle    = item.get('cle')
            valeur = item.get('valeur')
            if not cle or valeur is None:
                continue
            try:
                p = Parametre.objects.get(cle=cle)
                p.valeur = str(valeur)
                # Corriger la catégorie si elle est 'general' alors qu'elle devrait être autre
                if p.categorie == 'general' and cle in CATEGORIE_DEFAULTS:
                    p.categorie = CATEGORIE_DEFAULTS[cle]
                if p.type_valeur == 'str' and cle in TYPE_DEFAULTS:
                    p.type_valeur = TYPE_DEFAULTS[cle]
                p.save(update_fields=['valeur', 'categorie', 'type_valeur', 'updated_at'])
            except Parametre.DoesNotExist:
                # Inférer type_valeur
                tv = TYPE_DEFAULTS.get(cle)
                if not tv:
                    try: int(valeur); tv = 'int'
                    except (ValueError, TypeError):
                        try: float(valeur); tv = 'float'
                        except (ValueError, TypeError): tv = 'str'
                cat = item.get('categorie') or CATEGORIE_DEFAULTS.get(cle, 'general')
                Parametre.objects.create(
                    cle=cle, valeur=str(valeur),
                    type_valeur=tv, categorie=cat
                )
            updated.append(cle)
        return Response({'updated': updated})


from .models import Tournee
from rest_framework import serializers as drf_serializers


class TourneeSerializer(drf_serializers.ModelSerializer):
    agence_nom  = drf_serializers.CharField(source='agence.nom',  read_only=True)
    agence_code = drf_serializers.CharField(source='agence.code', read_only=True)

    class Meta:
        model  = Tournee
        fields = ['id', 'code', 'libelle', 'agence', 'agence_nom', 'agence_code',
                  'dotation', 'km_theorique', 'actif']


from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


class TourneeViewSet(ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = TourneeSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = filtrer_par_agence(Tournee.objects.select_related('agence'), self.request.user)
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        agence = self.request.query_params.get('agence')
        if agence:
            qs = qs.filter(agence__id=agence)
        return qs

    def perform_create(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        controler_agence(self.request.user, serializer.validated_data)
        serializer.save()

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

            try:
                obj, cree = Tournee.objects.update_or_create(
                    code=code[:20], defaults=valeurs
                )
                if cree:
                    crees += 1
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
        fields = ['id', 'code', 'libelle', 'actif']


class StatutVehiculeSerializer(drf_s2.ModelSerializer):
    class Meta:
        model  = StatutVehicule
        fields = ['id', 'code', 'libelle', 'couleur', 'actif']


class AffectationUsageViewSet(ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = AffectationUsageSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = AffectationUsage.objects.all()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


class StatutVehiculeViewSet(ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = StatutVehiculeSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = StatutVehicule.objects.all()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


class MarqueVehiculeSerializer(drf_s2.ModelSerializer):
    nb_modeles = drf_s2.SerializerMethodField()

    class Meta:
        model  = MarqueVehicule
        fields = ['id', 'libelle', 'actif', 'nb_modeles']

    def get_nb_modeles(self, obj):
        return obj.modeles.count()


class ModeleVehiculeSerializer(drf_s2.ModelSerializer):
    marque_libelle = drf_s2.CharField(source='marque.libelle', read_only=True)

    class Meta:
        model  = ModeleVehicule
        fields = ['id', 'marque', 'marque_libelle', 'libelle', 'actif']


class MarqueVehiculeViewSet(ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = MarqueVehiculeSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = MarqueVehicule.objects.all()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        return qs


class ModeleVehiculeViewSet(ReferentielPermissionMixin, viewsets.ModelViewSet):
    serializer_class   = ModeleVehiculeSerializer
    pagination_class   = None

    def get_queryset(self):
        qs = ModeleVehicule.objects.select_related('marque')
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=(actif.lower() == 'true'))
        marque = self.request.query_params.get('marque')
        if marque:
            qs = qs.filter(marque__id=marque)
        return qs

"""UbiFleet — Total Import Views"""

from rest_framework import mixins, viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters import rest_framework as df
from django.db.models import Count, Max, Min, Q, Sum

from .models import TransactionCarburant, ImportTotal
from .serializers import TransactionCarburantSerializer, ImportTotalSerializer
from .importeur import FichierInvalide, importer_fichier, lire_lignes
from apps.accounts.permissions import RoleBasedPermission, IsGestionnaire
from apps.core.agences import filtrer_par_agence, filtrer_transactions_total, voit_toutes_agences


class ImportTotalViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    """Historique des imports ; un import erroné se supprime avec ses transactions."""
    queryset           = ImportTotal.objects.select_related('importé_par').all()
    serializer_class   = ImportTotalSerializer
    module             = 'total_import'
    permission_classes = [IsGestionnaire]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['date_import', 'nb_importees']

    @action(
        detail=False, methods=['post'],
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload(self, request):
        """
        POST /total-import/upload/
        Paramètre : fichier (multipart)
        """
        if not voit_toutes_agences(request.user):
            raise PermissionDenied(
                "L'import concerne toutes les agences : réservé aux utilisateurs « Toutes les agences »."
            )
        fichier = request.FILES.get('fichier')
        if not fichier:
            return Response(
                {'detail': 'Aucun fichier fourni.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier l'extension
        nom = fichier.name.lower()
        if nom.endswith('.xls'):
            return Response({'detail': "Ancien format Excel (.xls) non pris en charge : enregistrez le fichier "
                                       "en .xlsx ou en .csv depuis Excel, puis importez-le."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not (nom.endswith('.csv') or nom.endswith('.xlsx')):
            return Response(
                {'detail': 'Format non supporté. Utilisez CSV ou Excel (.xlsx).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Si Excel, convertir en CSV via openpyxl
        fichier_bytes = fichier.read()
        if nom.endswith('.xlsx'):
            fichier_bytes = _excel_to_csv_bytes(fichier_bytes)
            if fichier_bytes is None:
                return Response(
                    {'detail': 'Impossible de lire le fichier Excel. Vérifiez le format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Fichier reconnu (colonnes indispensables présentes) avant de tracer l'import
        try:
            lire_lignes(fichier_bytes)
        except FichierInvalide as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Créer l'objet ImportTotal
        import_obj = ImportTotal.objects.create(
            fichier_nom=fichier.name,
            importé_par=request.user if request.user.is_authenticated else None,
        )

        # Lancer l'import
        result = importer_fichier(fichier_bytes, import_obj)

        # Mettre à jour les stats de l'import
        import_obj.nb_lignes    = result['importees'] + result['doublons'] + result['erreurs']
        import_obj.nb_importees = result['importees']
        import_obj.nb_doublons  = result['doublons']
        import_obj.nb_erreurs   = result['erreurs']
        import_obj.save()

        return Response({
            'import_id':    str(import_obj.id),
            'fichier':      fichier.name,
            'nb_lignes':    import_obj.nb_lignes,
            'importees':    result['importees'],
            'doublons':     result['doublons'],
            'erreurs':      result['erreurs'],
            'lignes_erreur': result['lignes_erreur'][:50],  # 50 premières erreurs affichées
            'colonnes_ignorees': result['colonnes_ignorees'],
        }, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Supprime un import et ses transactions (fichier importé par erreur)."""
        if not voit_toutes_agences(request.user):
            raise PermissionDenied("Réservé aux utilisateurs « Toutes les agences ».")
        obj = self.get_object()
        from django.db import transaction
        from .annulations import marquer_annulations
        with transaction.atomic():
            plaques = set(obj.transactions.values_list('immatriculation', flat=True))
            nb = obj.transactions.count()
            obj.transactions.all().delete()
            obj.delete()
            marquer_annulations(plaques)   # une annulation supprimée rend sa vente effective
        return Response({'detail': f"Import supprimé avec ses {nb} transaction(s)."}, status=status.HTTP_200_OK)


def _excel_to_csv_bytes(excel_bytes: bytes):
    """Convertit un fichier Excel en bytes CSV."""
    try:
        import openpyxl
        import csv
        import io

        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), read_only=True, data_only=True)
        ws = wb.active

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        import datetime as dt

        def texte(v):
            # Dates et heures Excel au format du fichier Total
            if isinstance(v, dt.datetime):
                return v.strftime('%H:%M:%S') if v.date() == dt.date(1899, 12, 30) else v.strftime('%d/%m/%Y %H:%M:%S')
            if isinstance(v, dt.date):
                return v.strftime('%d/%m/%Y')
            if isinstance(v, dt.time):
                return v.strftime('%H:%M:%S')
            return '' if v is None else str(v)

        for row in ws.iter_rows(values_only=True):
            writer.writerow([texte(v) for v in row])

        return output.getvalue().encode('utf-8-sig')
    except Exception:
        return None


class TransactionFilter(FilterSet):
    date_debut      = df.DateFilter(field_name='date_transaction', lookup_expr='gte')
    date_fin        = df.DateFilter(field_name='date_transaction', lookup_expr='lte')
    immatriculation = df.CharFilter(lookup_expr='iexact')
    nom_station     = df.CharFilter(lookup_expr='icontains')
    agence          = df.UUIDFilter(method='filtrer_agence')
    annulations     = df.ChoiceFilter(method='filtrer_annulations',
                                      choices=[('masquer', 'masquer'), ('seulement', 'seulement')])

    def filtrer_agence(self, qs, name, value):
        """Agence UbiFleet → son numéro client Total."""
        from apps.accounts.models import Agence
        numero = (Agence.objects.filter(pk=value).values_list('numero_client_total', flat=True).first() or '').strip()
        return qs.filter(numero_client=numero) if numero else qs.none()

    def filtrer_annulations(self, qs, name, value):
        """Annulation (volume négatif) et vente annulée (une annulation porte son code précédé de « - »)."""
        q = Q(est_annulation=True) | Q(est_annulee=True)
        return qs.exclude(q) if value == 'masquer' else qs.filter(q)

    class Meta:
        model = TransactionCarburant
        fields = ['immatriculation', 'numero_chauffeur', 'nom_station', 'nom_produit',
                  'statut_transaction', 'import_source']


class TransactionCarburantViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des transactions importées."""
    queryset         = TransactionCarburant.objects.select_related('import_source').all()
    serializer_class = TransactionCarburantSerializer
    module           = 'total_import'
    permission_classes = [IsGestionnaire]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = TransactionFilter
    search_fields    = [
        'immatriculation', 'nom_chauffeur', 'numero_ticket',
        'code_autorisation', 'nom_station',
    ]
    ordering_fields  = ['date_transaction', 'heure_transaction', 'montant', 'volume']

    def get_queryset(self):
        return filtrer_transactions_total(super().get_queryset(), self.request.user)

    def get_serializer_context(self):
        """Plaques du parc (normalisées) pour signaler les véhicules inconnus d'UbiFleet."""
        ctx = super().get_serializer_context()
        from apps.carburant.analyses import normaliser_immat
        from apps.vehicules.models import Vehicule
        ctx['plaques_parc'] = {normaliser_immat(i) for i in Vehicule.objects.values_list('immatriculation', flat=True)}
        return ctx

    @action(detail=False, methods=['get'])
    def valeurs(self, request):
        """Plaques et chauffeurs présents dans les transactions (listes des filtres)."""
        qs = self.get_queryset().order_by()
        plaques = sorted({p for p in qs.values_list('immatriculation', flat=True).distinct() if p})
        chauffeurs = sorted({(n or '', c or '') for n, c in qs.values_list('numero_chauffeur', 'nom_chauffeur')
                             .distinct() if n or c}, key=lambda x: (x[1], x[0]))
        return Response({'immatriculations': plaques,
                         'chauffeurs': [{'numero': n, 'nom': c} for n, c in chauffeurs]})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Synthèse des transactions filtrées : ventes effectives (hors annulations),
        annulations, plaques inconnues du parc UbiFleet."""
        from apps.carburant.analyses import normaliser_immat
        from apps.vehicules.models import Vehicule
        qs = self.filter_queryset(self.get_queryset())
        effectives = qs.exclude(Q(est_annulation=True) | Q(est_annulee=True))
        data = effectives.aggregate(nb_effectives=Count('id'), volume=Sum('volume'), montant=Sum('montant'))
        parc = {normaliser_immat(i) for i in Vehicule.objects.values_list('immatriculation', flat=True)}
        inconnues = {}
        for r in effectives.order_by().values('immatriculation').annotate(nb=Count('id'), volume=Sum('volume')):
            if normaliser_immat(r['immatriculation']) not in parc:
                inconnues[r['immatriculation']] = {'immatriculation': r['immatriculation'], 'nb': r['nb'],
                                                   'volume': float(r['volume'] or 0)}
        return Response({
            'nb_transactions': qs.count(),
            'nb_effectives': data['nb_effectives'],
            'volume': float(data['volume'] or 0),
            'montant': float(data['montant'] or 0),
            'nb_annulations': qs.filter(est_annulation=True).count(),
            'nb_annulees': qs.filter(est_annulee=True).count(),
            'periode': qs.aggregate(debut=Min('date_transaction'), fin=Max('date_transaction')),
            'plaques_inconnues': sorted(inconnues.values(), key=lambda x: -x['nb']),
        })

"""UbiFleet — Total Import Views"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters import rest_framework as df
from django.db.models import Sum, Count

from .models import TransactionCarburant, ImportTotal
from .serializers import TransactionCarburantSerializer, ImportTotalSerializer
from .importeur import importer_fichier
from apps.accounts.permissions import RoleBasedPermission, IsGestionnaire
from apps.core.agences import filtrer_par_agence, filtrer_transactions_total, voit_toutes_agences


class ImportTotalViewSet(viewsets.ReadOnlyModelViewSet):
    """Historique des imports."""
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
        if not (nom.endswith('.csv') or nom.endswith('.xlsx') or nom.endswith('.xls')):
            return Response(
                {'detail': 'Format non supporté. Utilisez CSV ou Excel (.xlsx/.xls).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Si Excel, convertir en CSV via openpyxl
        fichier_bytes = fichier.read()
        if nom.endswith('.xlsx') or nom.endswith('.xls'):
            fichier_bytes = _excel_to_csv_bytes(fichier_bytes)
            if fichier_bytes is None:
                return Response(
                    {'detail': 'Impossible de lire le fichier Excel. Vérifiez le format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

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
            'lignes_erreur': result['lignes_erreur'][:20],  # max 20 erreurs affichées
        }, status=status.HTTP_201_CREATED)


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
        for row in ws.iter_rows(values_only=True):
            writer.writerow(['' if v is None else str(v) for v in row])

        return output.getvalue().encode('utf-8-sig')
    except Exception:
        return None


class TransactionFilter(FilterSet):
    date_debut      = df.DateFilter(field_name='date_transaction', lookup_expr='gte')
    date_fin        = df.DateFilter(field_name='date_transaction', lookup_expr='lte')
    immatriculation = df.CharFilter(lookup_expr='iexact')
    nom_station     = df.CharFilter(lookup_expr='icontains')

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
        """Statistiques globales des transactions."""
        qs = self.filter_queryset(self.get_queryset())
        data = qs.aggregate(
            total_transactions = Count('id'),
            total_volume       = Sum('volume'),
            total_montant      = Sum('montant'),
        )
        # Stats par véhicule
        par_vehicule = list(
            qs.values('immatriculation')
              .annotate(
                  nb=Count('id'),
                  volume=Sum('volume'),
                  montant=Sum('montant')
              )
              .order_by('-montant')[:20]
        )
        # Stats par station
        par_station = list(
            qs.values('nom_station')
              .annotate(nb=Count('id'), montant=Sum('montant'))
              .order_by('-montant')[:10]
        )
        # Stats par produit
        par_produit = list(
            qs.values('nom_produit')
              .annotate(nb=Count('id'), volume=Sum('volume'))
              .order_by('-volume')
        )
        return Response({
            **data,
            'par_vehicule': par_vehicule,
            'par_station':  par_station,
            'par_produit':  par_produit,
        })

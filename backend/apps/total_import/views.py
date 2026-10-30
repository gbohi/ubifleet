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
    def consommation(self, request):
        """
        Calcul de la consommation aux 100 km par véhicule entre deux dates.
        Formule : (volume total / km parcourus) * 100
        Paramètres : date_debut, date_fin, immatriculation (optionnel), chauffeur (optionnel)
        """
        from django.db.models import Min, Max
        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        immat      = request.query_params.get('immatriculation', '')
        chauffeur  = request.query_params.get('chauffeur', '')

        if not date_debut or not date_fin:
            return Response(
                {'detail': 'Les paramètres date_debut et date_fin sont requis.'},
                status=400
            )

        # Toutes les transactions sur la période (pas de filtre sur statut)
        qs = filtrer_transactions_total(TransactionCarburant.objects.filter(
            date_transaction__gte=date_debut,
            date_transaction__lte=date_fin,
        ).exclude(immatriculation='').exclude(immatriculation__isnull=True), request.user)
        if immat:     qs = qs.filter(immatriculation__icontains=immat)
        if chauffeur: qs = qs.filter(nom_chauffeur__icontains=chauffeur)

        resultats = []
        for vehicule_data in (
            qs.values('immatriculation')
              .annotate(
                  volume_total    = Sum('volume'),
                  montant_total   = Sum('montant'),
                  nb_pleins       = Count('id'),
                  km_debut        = Min('kilometrage_precedent'),
                  km_fin          = Max('kilometrage_actuel'),
              )
              .filter(volume_total__gt=0)
              .order_by('immatriculation')
        ):
            km_debut = vehicule_data['km_debut'] or 0
            km_fin   = vehicule_data['km_fin'] or 0
            km_parcourus = float(km_fin) - float(km_debut) if km_fin > km_debut else 0
            volume = float(vehicule_data['volume_total'] or 0)

            conso_100 = round((volume / km_parcourus) * 100, 2) if km_parcourus > 0 else None

            resultats.append({
                'immatriculation':  vehicule_data['immatriculation'],
                'km_debut':         float(km_debut),
                'km_fin':           float(km_fin),
                'km_parcourus':     round(km_parcourus, 0),
                'volume_total':     round(volume, 2),
                'montant_total':    float(vehicule_data['montant_total'] or 0),
                'nb_pleins':        vehicule_data['nb_pleins'],
                'conso_100':        conso_100,
            })

        return Response({
            'periode':   {'debut': date_debut, 'fin': date_fin},
            'nb_vehicules': len(resultats),
            'resultats':  sorted(resultats, key=lambda x: x['conso_100'] or 0, reverse=True),
        })

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

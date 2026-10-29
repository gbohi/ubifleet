"""UbiFleet — Grand Livre Views"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count

from .models import ImportGrandLivre, LigneGrandLivre
from .serializers import ImportGrandLivreSerializer, LigneGrandLivreSerializer
from .importeur import importer_grand_livre
from apps.accounts.permissions import IsGestionnaire


class ImportGrandLivreViewSet(viewsets.ReadOnlyModelViewSet):
    """Historique des imports de grand livre."""
    queryset           = ImportGrandLivre.objects.select_related('importe_par').all()
    serializer_class   = ImportGrandLivreSerializer
    permission_classes = [IsGestionnaire]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['date_import']

    @action(
        detail=False, methods=['post'],
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload(self, request):
        """POST /grand-livre/imports/upload/"""
        fichier = request.FILES.get('fichier')
        if not fichier:
            return Response({'detail': 'Aucun fichier fourni.'}, status=400)

        nom = fichier.name.lower()
        if not (nom.endswith('.xls') or nom.endswith('.xlsx') or nom.endswith('.csv')):
            return Response(
                {'detail': 'Format non supporté. Utilisez XLS, XLSX ou CSV.'},
                status=400
            )

        fichier_bytes = fichier.read()

        import_obj = ImportGrandLivre.objects.create(
            fichier_nom=fichier.name,
            importe_par=request.user if request.user.is_authenticated else None,
        )

        try:
            result = importer_grand_livre(fichier_bytes, fichier.name, import_obj)
        except Exception as exc:
            import_obj.delete()
            return Response({'detail': str(exc)}, status=400)

        import_obj.nb_lignes    = result['importees'] + result['doublons'] + result['erreurs']
        import_obj.nb_importees = result['importees']
        import_obj.nb_doublons  = result['doublons']
        import_obj.nb_erreurs   = result['erreurs']
        import_obj.save()

        return Response({
            'import_id':     str(import_obj.id),
            'fichier':       fichier.name,
            'code_agence':   result['code_agence'],
            'libelle_agence':result['libelle_agence'],
            'nb_lignes':     import_obj.nb_lignes,
            'importees':     result['importees'],
            'doublons':      result['doublons'],
            'erreurs':       result['erreurs'],
            'lignes_erreur': result['lignes_erreur'][:20],
        }, status=201)


class LigneGrandLivreViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des lignes du grand livre."""
    queryset         = LigneGrandLivre.objects.select_related('import_source').all()
    serializer_class = LigneGrandLivreSerializer
    permission_classes = [IsGestionnaire]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'code_agence', 'compte', 'origine',
        'date_analytique', 'date_comptable', 'import_source',
    ]
    search_fields    = [
        'compte', 'libelle_compte', 'piece',
        'libelle_ecriture', 'code_agence', 'libelle_agence',
    ]
    ordering_fields  = ['date_analytique', 'date_comptable', 'compte', 'debit', 'credit']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques globales, par agence, par compte, par agence+compte."""
        qs = self.filter_queryset(self.get_queryset())

        agg = qs.aggregate(
            nb_lignes    = Count('id'),
            total_debit  = Sum('debit'),
            total_credit = Sum('credit'),
        )

        par_agence = list(
            qs.values('code_agence', 'libelle_agence')
              .annotate(nb=Count('id'), debit=Sum('debit'), credit=Sum('credit'))
              .order_by('code_agence')
        )
        # Convertir Decimal → float pour JSON
        for r in par_agence:
            r['debit']  = float(r['debit']  or 0)
            r['credit'] = float(r['credit'] or 0)
            r['solde']  = round(r['debit'] - r['credit'], 2)

        par_compte = list(
            qs.values('compte', 'libelle_compte')
              .annotate(nb=Count('id'), debit=Sum('debit'), credit=Sum('credit'))
              .order_by('compte')
        )
        for r in par_compte:
            r['debit']  = float(r['debit']  or 0)
            r['credit'] = float(r['credit'] or 0)
            r['solde']  = round(r['debit'] - r['credit'], 2)

        par_agence_compte = list(
            qs.values('code_agence', 'libelle_agence', 'compte', 'libelle_compte')
              .annotate(nb=Count('id'), debit=Sum('debit'), credit=Sum('credit'))
              .order_by('code_agence', 'compte')
        )
        for r in par_agence_compte:
            r['debit']  = float(r['debit']  or 0)
            r['credit'] = float(r['credit'] or 0)
            r['solde']  = round(r['debit'] - r['credit'], 2)

        par_origine = list(
            qs.values('origine')
              .annotate(nb=Count('id'), debit=Sum('debit'), credit=Sum('credit'))
              .order_by('-debit')
        )
        for r in par_origine:
            r['debit']  = float(r['debit']  or 0)
            r['credit'] = float(r['credit'] or 0)

        total_debit  = float(agg['total_debit']  or 0)
        total_credit = float(agg['total_credit'] or 0)

        return Response({
            'nb_lignes':         agg['nb_lignes'] or 0,
            'total_debit':       total_debit,
            'total_credit':      total_credit,
            'solde':             round(total_debit - total_credit, 2),
            'par_agence':        par_agence,
            'par_compte':        par_compte,
            'par_agence_compte': par_agence_compte,
            'par_origine':       par_origine,
        })

"""UbiFleet — Total Import Views"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
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


class TransactionCarburantViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des transactions importées."""
    queryset         = TransactionCarburant.objects.select_related('import_source').all()
    serializer_class = TransactionCarburantSerializer
    module           = 'total_import'
    permission_classes = [IsGestionnaire]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'immatriculation', 'nom_chauffeur', 'nom_station',
        'nom_produit', 'statut_transaction', 'date_transaction',
        'import_source',
    ]
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
    def evolution_agences(self, request):
        """
        Évolution des prises de carburant par agence entre deux dates.
        Retourne une série temporelle (par mois) pour chaque agence.
        Paramètres : date_debut, date_fin, immatriculation (optionnel), chauffeur (optionnel)
        """
        from django.db.models.functions import TruncMonth
        from apps.accounts.models import Agence

        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        immat      = request.query_params.get('immatriculation', '')
        num_chauf  = request.query_params.get('numero_chauffeur_total', '').strip()

        if not date_debut or not date_fin:
            return Response(
                {'detail': 'Les paramètres date_debut et date_fin sont requis.'},
                status=400
            )

        qs = filtrer_transactions_total(TransactionCarburant.objects.filter(
            date_transaction__gte=date_debut,
            date_transaction__lte=date_fin,
        ), request.user)
        if immat:     qs = qs.filter(immatriculation__icontains=immat)
        if num_chauf: qs = qs.filter(numero_chauffeur__icontains=num_chauf)

        # Récupérer les agences avec leur numero_client_total
        agences = {
            a.numero_client_total: a.nom
            for a in Agence.objects.filter(numero_client_total__gt='', is_active=True)
        }

        # Grouper par client Total (= agence) + mois
        series = (
            qs.annotate(mois=TruncMonth('date_transaction'))
              .values('numero_client', 'mois')
              .annotate(
                  volume=Sum('volume'),
                  montant=Sum('montant'),
                  nb=Count('id'),
              )
              .order_by('numero_client', 'mois')
        )

        # Structurer par agence
        agences_data: dict = {}
        for row in series:
            client_num = str(row['numero_client'] or '').strip()
            agence_nom = agences.get(client_num, f"Client {client_num or '?'}")
            mois_str   = row['mois'].strftime('%Y-%m') if row['mois'] else '?'

            if agence_nom not in agences_data:
                agences_data[agence_nom] = {
                    'nom':    agence_nom,
                    'client': client_num,
                    'points': [],
                }
            agences_data[agence_nom]['points'].append({
                'mois':    mois_str,
                'volume':  float(row['volume'] or 0),
                'montant': float(row['montant'] or 0),
                'nb':      row['nb'],
            })

        return Response({
            'periode':  {'debut': date_debut, 'fin': date_fin},
            'agences':  list(agences_data.values()),
        })

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


class ReconciliationViewSet(viewsets.ViewSet):
    """
    Réconciliation transactions Total vs pleins UbiFleet.
    Endpoint : GET /total-import/reconciliation/?date_debut=&date_fin=&immatriculation=&seuil_volume=&seuil_montant=
    """
    permission_classes = [IsGestionnaire]

    @action(detail=False, methods=['get'])
    def comparer(self, request):
        """
        Compare les transactions Total aux pleins UbiFleet sur une période.

        Logique de rapprochement :
        - Jointure par immatriculation + date (±1 jour)
        - Seuil écart volume : % de différence toléré (défaut 5%)
        - Seuil écart montant : % de différence toléré (défaut 5%)

        Statuts retournés :
        - reconcilie    : trouvé des deux côtés, écarts dans les seuils
        - ecart_volume  : écart de volume > seuil
        - ecart_montant : écart de montant > seuil
        - double_ecart  : écarts volume ET montant
        - total_only    : dans Total mais pas dans UbiFleet
        - ubifleet_only : dans UbiFleet mais pas dans Total
        """
        from apps.carburant.models import PleinsCarburant
        from datetime import datetime, timedelta
        import math

        date_debut   = request.query_params.get('date_debut')
        date_fin     = request.query_params.get('date_fin')
        immat        = request.query_params.get('immatriculation', '').strip()
        num_chauf    = request.query_params.get('numero_chauffeur_total', '').strip()
        seuil_vol    = float(request.query_params.get('seuil_volume', 5))
        seuil_mnt    = float(request.query_params.get('seuil_montant', 5))

        if not date_debut or not date_fin:
            return Response({'detail': 'date_debut et date_fin sont requis.'}, status=400)

        # ── Transactions Total ──────────────────────────────────────────
        qs_total = filtrer_transactions_total(TransactionCarburant.objects.filter(
            date_transaction__gte=date_debut,
            date_transaction__lte=date_fin,
        ).exclude(immatriculation='').exclude(immatriculation__isnull=True), request.user)

        if immat:     qs_total = qs_total.filter(immatriculation__icontains=immat)
        if num_chauf: qs_total = qs_total.filter(numero_chauffeur__icontains=num_chauf)

        total_rows = list(qs_total.values(
            'id', 'immatriculation', 'date_transaction', 'heure_transaction',
            'volume', 'montant', 'nom_station', 'numero_ticket',
            'numero_chauffeur', 'nom_chauffeur', 'nom_produit',
        ))

        # ── Pleins UbiFleet ─────────────────────────────────────────────
        qs_ubi = filtrer_par_agence(PleinsCarburant.objects.filter(
            date_plein__gte=date_debut,
            date_plein__lte=date_fin,
        ).select_related('vehicule', 'chauffeur', 'station'), request.user)

        if immat: qs_ubi = qs_ubi.filter(vehicule__immatriculation__icontains=immat)

        ubi_rows = list(qs_ubi.values(
            'id', 'vehicule__immatriculation', 'date_plein',
            'volume_litres', 'montant_fcfa', 'bon_carburant',
            'chauffeur__nom', 'chauffeur__prenom',
            'chauffeur__numero_chauffeur_total',
            'statut_validation',
        ))

        # ── Rapprochement ───────────────────────────────────────────────
        # Indexer UbiFleet par (immatriculation, date)
        ubi_index: dict = {}
        for row in ubi_rows:
            key = (
                str(row['vehicule__immatriculation'] or '').upper().strip(),
                str(row['date_plein']),
            )
            ubi_index.setdefault(key, []).append(row)

        used_ubi_ids = set()
        lignes = []

        for t in total_rows:
            immat_key = str(t['immatriculation'] or '').upper().strip()
            date_str  = str(t['date_transaction'])

            # Chercher dans UbiFleet à ±1 jour
            match = None
            for delta in [0, 1, -1]:
                try:
                    d = datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=delta)
                    test_key = (immat_key, d.strftime('%Y-%m-%d'))
                    candidates = [r for r in ubi_index.get(test_key, []) if r['id'] not in used_ubi_ids]
                    if candidates:
                        match = candidates[0]
                        break
                except Exception:
                    pass

            vol_total = float(t['volume'] or 0)
            mnt_total = float(t['montant'] or 0)

            if match:
                used_ubi_ids.add(match['id'])
                vol_ubi = float(match['volume_litres'] or 0)
                mnt_ubi = float(match['montant_fcfa'] or 0)

                ecart_vol = abs(vol_total - vol_ubi)
                ecart_mnt = abs(mnt_total - mnt_ubi)
                pct_vol   = (ecart_vol / vol_total * 100) if vol_total > 0 else 0
                pct_mnt   = (ecart_mnt / mnt_total * 100) if mnt_total > 0 else 0

                ev = pct_vol > seuil_vol
                em = pct_mnt > seuil_mnt

                if ev and em:   statut = 'double_ecart'
                elif ev:        statut = 'ecart_volume'
                elif em:        statut = 'ecart_montant'
                else:           statut = 'reconcilie'

                lignes.append({
                    'statut':           statut,
                    'immatriculation':  immat_key,
                    'date':             date_str,
                    'heure':            str(t['heure_transaction'] or ''),
                    # Total
                    'total_ticket':     t['numero_ticket'],
                    'total_volume':     vol_total,
                    'total_montant':    mnt_total,
                    'total_station':    t['nom_station'],
                    'total_produit':    t['nom_produit'],
                    'total_chauffeur':  t['nom_chauffeur'],
                    'total_num_chauf':  t['numero_chauffeur'],
                    # UbiFleet
                    'ubi_bon':          match['bon_carburant'],
                    'ubi_volume':       vol_ubi,
                    'ubi_montant':      mnt_ubi,
                    'ubi_chauffeur':    f"{match['chauffeur__prenom'] or ''} {match['chauffeur__nom'] or ''}".strip(),
                    'ubi_statut':       match['statut_validation'],
                    # Écarts
                    'ecart_volume':     round(vol_total - vol_ubi, 2),
                    'ecart_montant':    round(mnt_total - mnt_ubi, 0),
                    'pct_volume':       round(pct_vol, 1),
                    'pct_montant':      round(pct_mnt, 1),
                })
            else:
                # Présent dans Total seulement
                lignes.append({
                    'statut':          'total_only',
                    'immatriculation': immat_key,
                    'date':            date_str,
                    'heure':           str(t['heure_transaction'] or ''),
                    'total_ticket':    t['numero_ticket'],
                    'total_volume':    vol_total,
                    'total_montant':   mnt_total,
                    'total_station':   t['nom_station'],
                    'total_produit':   t['nom_produit'],
                    'total_chauffeur': t['nom_chauffeur'],
                    'total_num_chauf': t['numero_chauffeur'],
                    'ubi_bon':         None,
                    'ubi_volume':      None,
                    'ubi_montant':     None,
                    'ubi_chauffeur':   None,
                    'ubi_statut':      None,
                    'ecart_volume':    vol_total,
                    'ecart_montant':   mnt_total,
                    'pct_volume':      100,
                    'pct_montant':     100,
                })

        # Pleins UbiFleet sans correspondance Total
        for row in ubi_rows:
            if row['id'] in used_ubi_ids:
                continue
            immat_key = str(row['vehicule__immatriculation'] or '').upper().strip()
            vol_ubi   = float(row['volume_litres'] or 0)
            mnt_ubi   = float(row['montant_fcfa'] or 0)
            lignes.append({
                'statut':          'ubifleet_only',
                'immatriculation': immat_key,
                'date':            str(row['date_plein']),
                'heure':           '',
                'total_ticket':    None,
                'total_volume':    None,
                'total_montant':   None,
                'total_station':   None,
                'total_produit':   None,
                'total_chauffeur': None,
                'total_num_chauf': None,
                'ubi_bon':         row['bon_carburant'],
                'ubi_volume':      vol_ubi,
                'ubi_montant':     mnt_ubi,
                'ubi_chauffeur':   f"{row['chauffeur__prenom'] or ''} {row['chauffeur__nom'] or ''}".strip(),
                'ubi_statut':      row['statut_validation'],
                'ecart_volume':    -vol_ubi,
                'ecart_montant':   -mnt_ubi,
                'pct_volume':      100,
                'pct_montant':     100,
            })

        # Trier par date puis immatriculation
        lignes.sort(key=lambda x: (x['date'], x['immatriculation']))

        # Statistiques globales
        nb = len(lignes)
        stats = {
            'total':           nb,
            'reconcilie':      sum(1 for l in lignes if l['statut'] == 'reconcilie'),
            'ecart_volume':    sum(1 for l in lignes if l['statut'] == 'ecart_volume'),
            'ecart_montant':   sum(1 for l in lignes if l['statut'] == 'ecart_montant'),
            'double_ecart':    sum(1 for l in lignes if l['statut'] == 'double_ecart'),
            'total_only':      sum(1 for l in lignes if l['statut'] == 'total_only'),
            'ubifleet_only':   sum(1 for l in lignes if l['statut'] == 'ubifleet_only'),
            'total_ecart_vol': round(sum(
                l['ecart_volume'] for l in lignes
                if l['statut'] in ['ecart_volume','double_ecart','total_only']
            ), 2),
            'total_ecart_mnt': round(sum(
                l['ecart_montant'] for l in lignes
                if l['statut'] in ['ecart_montant','double_ecart','total_only']
            ), 0),
        }

        return Response({
            'periode':   {'debut': date_debut, 'fin': date_fin},
            'seuils':    {'volume': seuil_vol, 'montant': seuil_mnt},
            'stats':     stats,
            'lignes':    lignes,
        })

"""UbiFleet — Grand Livre : import et filtres."""
import datetime
import io
from decimal import Decimal

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from .importeur import _parse_date, _parse_decimal
from .models import ImportGrandLivre, LigneGrandLivre

ENTETE = ['Compte', 'Libellé', 'Analytique', 'Comptable', 'Origine', 'Pièce',
          'N° ligne', 'N° analytique', 'Libellé écriture', 'Débit', 'Crédit', 'Solde']


def fichier_xlsx(lignes, agence=('ABJ', 'CENTRALE')):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(ENTETE)
    ws.append(list(agence))
    for l in lignes:
        ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile('gl.xlsx', buf.getvalue())


class ImporteurTests(APITestCase):
    def test_conversions(self):
        self.assertEqual(_parse_date(datetime.datetime(2026, 1, 5, 0, 0)), datetime.date(2026, 1, 5))
        self.assertEqual(_parse_date('2026-01-05 00:00:00'), datetime.date(2026, 1, 5))
        self.assertEqual(_parse_date('05/01/2026'), datetime.date(2026, 1, 5))
        self.assertEqual(_parse_date(46027.0), datetime.date(2026, 1, 5))
        self.assertIsNone(_parse_date(''))
        self.assertEqual(_parse_decimal('1 234,50'), Decimal('1234.50'))
        self.assertEqual(_parse_decimal('1.234,50'), Decimal('1234.50'))
        self.assertEqual(_parse_decimal(15000.0), Decimal('15000.00'))


class GrandLivreTests(UtilisateursMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.flotte_global = cls.creer_utilisateur('flotte_global', 'responsable_flotte', None)

    def setUp(self):
        self.client.force_authenticate(self.flotte_global)

    def importer(self, fichier):
        return self.client.post(reverse('gl-import-upload'), {'fichier': fichier}, format='multipart')

    def test_import_xlsx_dates_comptes_et_doublons(self):
        lignes = [
            [606100.0, 'Carburant', datetime.datetime(2026, 1, 5), datetime.datetime(2026, 1, 6),
             'ACH', 'P1', 1, 1, 'Plein', 15000, None, 15000],
            ['624100', 'Transport', '10/02/2026', '10/02/2026', 'BQ', 'P2', 1, 1, 'Course', '2 500,00', '', ''],
            ['Solde du compte', None, None, None, None, None, None, None, None, 17500, 0, None],
            ['606100', 'Carburant', 'pas une date', '', 'ACH', 'P3', 1, 1, 'X', 1, 0, 0],
        ]
        resp = self.importer(fichier_xlsx(lignes))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((resp.data['importees'], resp.data['erreurs']), (2, 1))
        l1 = LigneGrandLivre.objects.get(piece='P1')
        self.assertEqual((l1.compte, l1.date_comptable, l1.debit), ('606100', datetime.date(2026, 1, 6), Decimal('15000')))
        imp = ImportGrandLivre.objects.get()
        self.assertEqual(imp.code_agence, 'ABJ')

        # Ré-import : tout est en doublon
        resp = self.importer(fichier_xlsx(lignes[:2]))
        self.assertEqual((resp.data['importees'], resp.data['doublons']), (0, 2))

    def test_filtres_periode_compte_et_options(self):
        self.importer(fichier_xlsx([
            ['606100', 'Carburant', '05/01/2026', '05/01/2026', 'ACH', 'P1', 1, 1, 'a', 100, 0, 0],
            ['606200', 'Lubrifiants', '05/02/2026', '05/02/2026', 'ACH', 'P2', 1, 1, 'b', 200, 0, 0],
            ['401000', 'Fournisseurs', '05/03/2026', '05/03/2026', 'BQ', 'P3', 1, 1, 'c', 0, 300, 0],
        ]))
        url = reverse('gl-ligne-list')
        pieces = lambda **p: sorted(l['piece'] for l in self.client.get(url, p).data['results'])
        self.assertEqual(pieces(date_debut='2026-02-01', date_fin='2026-02-28'), ['P2'])
        self.assertEqual(pieces(compte='606'), ['P1', 'P2'])
        self.assertEqual(pieces(origine='bq'), ['P3'])
        self.assertEqual(pieces(code_agence='abj'), ['P1', 'P2', 'P3'])

        stats = self.client.get(reverse('gl-ligne-stats'), {'compte': '6'}).data
        self.assertEqual(stats['total_debit'], 300)
        self.assertEqual([m['mois'] for m in stats['par_mois']], ['2026-01', '2026-02'])

        opts = self.client.get(reverse('gl-ligne-options')).data
        self.assertEqual(opts['origines'], ['ACH', 'BQ'])
        self.assertEqual(str(opts['date_debut']), '2026-01-05')

    def test_suppression_import(self):
        self.importer(fichier_xlsx([['606100', 'C', '05/01/2026', '05/01/2026', 'ACH', 'P1', 1, 1, 'a', 100, 0, 0]]))
        imp = ImportGrandLivre.objects.get()
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.delete(reverse('gl-import-detail', args=[imp.pk])).status_code, 403)
        self.client.force_authenticate(self.flotte_global)
        self.assertEqual(self.client.delete(reverse('gl-import-detail', args=[imp.pk])).status_code, 204)
        self.assertEqual(LigneGrandLivre.objects.count(), 0)

    def test_historique_cloisonne(self):
        ImportGrandLivre.objects.create(fichier_nom='a.xlsx', code_agence='ABJ')
        ImportGrandLivre.objects.create(fichier_nom='b.xlsx', code_agence='BKE')
        self.client.force_authenticate(self.gestionnaire)
        noms = [i['fichier_nom'] for i in self.client.get(reverse('gl-import-list')).data['results']]
        self.assertEqual(noms, ['a.xlsx'])

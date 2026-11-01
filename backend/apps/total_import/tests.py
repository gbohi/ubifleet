"""UbiFleet — Tests de l'import des transactions TotalEnergies."""

import io

from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from .importeur import COLUMN_MAP
from .models import ImportTotal, TransactionCarburant

URL = '/api/v1/total-import/'
ENTETES = list(COLUMN_MAP)


def ligne(**v):
    base = {'Numéro de ticket': '1', "Code d'autorisation": '100', 'Date de transaction': '28/05/2026',
            'Heure de la transaction': '08:00', "Plaque d'immatriculation": '56317 WW 01', 'Volume': '40,00',
            'Montant': '27 000', 'No. du client': '132', 'Statut de transaction': 'Paiement réconcilié'}
    base.update(v)
    return [base.get(c, '') for c in ENTETES]


def fichier(lignes, entetes=ENTETES, nom='total.csv'):
    contenu = '\n'.join(';'.join(r) for r in [entetes, *lignes])
    f = io.BytesIO(contenu.encode('utf-8-sig'))
    f.name = nom
    return f


class ImportTotalTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.global_ = cls.creer_utilisateur('global_total', 'responsable_flotte', None)   # toutes agences

    def setUp(self):
        self.client.force_authenticate(self.global_)

    def importer(self, f):
        return self.client.post(f'{URL}historique/upload/', {'fichier': f}, format='multipart')

    def test_import_annulations_et_doublons(self):
        r = self.importer(fichier([
            ligne(),
            ligne(**{'Numéro de ticket': '2', "Code d'autorisation": '-100', 'Volume': '-40', 'Montant': '-27000',
                     'Heure de la transaction': '08:05'}),                                   # annulation auto
            ligne(**{'Numéro de ticket': '3', "Code d'autorisation": '200', 'Heure de la transaction': '09:00',
                     'Volume': '15', 'Montant': '10125'}),
            ligne(**{'Numéro de ticket': '4', "Code d'autorisation": '201', 'Heure de la transaction': '09:10',
                     'Volume': '-15', 'Montant': '-10125'}),                                 # annulation manuelle
            ligne(**{'Numéro de ticket': '5', "Code d'autorisation": '300', 'Heure de la transaction': '10:00'}),
            ligne(**{'Date de transaction': 'pas une date', 'Numéro de ticket': '6'}),
        ]))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['importees'], r.data['erreurs']), (5, 1))
        self.assertIn('Date', r.data['lignes_erreur'][0]['erreur'])
        annulees = set(TransactionCarburant.objects.filter(est_annulee=True).values_list('numero_ticket', flat=True))
        self.assertEqual(annulees, {'1', '3'})
        s = self.client.get(f'{URL}transactions/stats/').data
        self.assertEqual((s['nb_transactions'], s['nb_effectives'], s['volume']), (5, 1, 40.0))
        self.assertEqual(self.client.get(f'{URL}transactions/', {'annulations': 'masquer'}).data['count'], 1)
        # Réimport du même fichier : tout en doublon
        r = self.importer(fichier([ligne()]))
        self.assertEqual((r.data['importees'], r.data['doublons']), (0, 1))

    def test_fichier_non_reconnu_refuse(self):
        r = self.importer(fichier([['a', 'b']], entetes=['Date', 'Montant']))
        self.assertEqual(r.status_code, 400)
        self.assertIn('colonne(s) manquante(s)', r.data['detail'])
        self.assertFalse(ImportTotal.objects.exists())
        self.assertEqual(self.importer(fichier([ligne()], nom='ancien.xls')).status_code, 400)

    def test_entetes_tolerants_et_excel(self):
        import datetime
        import openpyxl
        entetes = [c.upper().replace('É', 'E') + ' ' for c in ENTETES]      # casse, accents, espaces
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(entetes)
        valeurs = ligne()
        valeurs[ENTETES.index('Date de transaction')] = datetime.datetime(2026, 5, 28)
        valeurs[ENTETES.index('Heure de la transaction')] = datetime.time(8, 30)
        valeurs[ENTETES.index('Volume')] = 40.0
        ws.append(valeurs)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'total.xlsx'
        r = self.importer(buf)
        self.assertEqual(r.status_code, 201, r.data)
        t = TransactionCarburant.objects.get()
        self.assertEqual((t.date_transaction, t.heure_transaction), (datetime.date(2026, 5, 28), datetime.time(8, 30)))

    def test_suppression_import(self):
        self.importer(fichier([ligne(), ligne(**{'Numéro de ticket': '2', "Code d'autorisation": '-100',
                                                 'Volume': '-40', 'Montant': '-27000'})]))
        imp = ImportTotal.objects.get()
        self.client.force_authenticate(self.operateur_b)
        self.assertIn(self.client.delete(f'{URL}historique/{imp.id}/').status_code, (403, 404))
        self.client.force_authenticate(self.global_)
        r = self.client.delete(f'{URL}historique/{imp.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(TransactionCarburant.objects.exists())

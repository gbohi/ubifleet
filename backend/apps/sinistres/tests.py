"""UbiFleet — Tests Sinistres : déclaration, contrôles, statut, pièces jointes, contrats."""

import datetime
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.chauffeurs.models import Chauffeur
from apps.core.testing import UtilisateursMixin
from apps.vehicules.models import Vehicule
from .models import Assureur, ContratAssurance, Sinistre

MEDIA = tempfile.mkdtemp()
URL = '/api/v1/sinistres/'


@override_settings(MEDIA_ROOT=MEDIA)
class SinistreTests(UtilisateursMixin, APITestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.v = Vehicule.objects.create(immatriculation='SI-1', agence=cls.agence_a, annee=2020)
        cls.autre = Vehicule.objects.create(immatriculation='SI-2', agence=cls.agence_a, annee=2020)
        cls.assureur = Assureur.objects.create(nom='NSIA test')
        cls.contrat = ContratAssurance.objects.create(vehicule=cls.autre, assureur=cls.assureur, numero_police='P1',
                                                      type_contrat='rc', date_debut='2026-01-01', date_fin='2026-12-31',
                                                      prime_annuelle=100000)

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def declarer(self, **extra):
        return self.client.post(f'{URL}sinistres/', {'vehicule': str(self.v.id), 'type_sinistre': 'accident',
                                                     'date_sinistre': '2026-05-01', 'description': 'Choc',
                                                     'dommages_estimes': 100000, **extra}, format='json')

    def test_declaration_controles_et_numero(self):
        r = self.declarer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(str(r.data['agence']), str(self.agence_a.id))
        # Contrat d'un autre véhicule, date future, montant négatif, chauffeur d'une autre agence : refusés
        self.assertIn('contrat_assurance', self.declarer(contrat_assurance=str(self.contrat.id)).data)
        futur = (timezone.localdate() + datetime.timedelta(days=2)).isoformat()
        self.assertIn('date_sinistre', self.declarer(date_sinistre=futur).data)
        self.assertEqual(self.declarer(cout_reparation=-1).status_code, 400)
        c = Chauffeur.objects.create(matricule='SI-C', nom='N', prenom='P', numero_permis='X', categories_permis='B',
                                     agence=self.agence_b)
        self.assertIn('chauffeur', self.declarer(chauffeur=str(c.id)).data)
        # Numéro de dossier unique même après suppression
        r2 = self.declarer()
        Sinistre.objects.filter(pk=r.data['id']).delete()
        r3 = self.declarer()
        self.assertEqual(r3.status_code, 201, r3.data)
        self.assertNotEqual(r2.data['numero_dossier'], r3.data['numero_dossier'])

    def test_statut_cloture_et_notes(self):
        s = self.declarer(cout_reparation=500000, indemnisation_recue=300000).data
        self.assertEqual(s['reste_a_charge'], 200000)
        r = self.client.post(f"{URL}sinistres/{s['id']}/changer_statut/", {'statut': 'indemnise', 'notes': 'Chèque reçu'},
                             format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNotNone(r.data['date_cloture'])
        self.assertIn('Chèque reçu', r.data['notes'])
        r = self.client.post(f"{URL}sinistres/{s['id']}/changer_statut/", {'statut': 'conteste'}, format='json')
        self.assertIsNone(r.data['date_cloture'])          # rouvert
        self.assertEqual(self.client.post(f"{URL}sinistres/{s['id']}/changer_statut/", {'statut': 'conteste'},
                                          format='json').status_code, 400)
        # Le statut ne se change pas par la modification du dossier
        self.client.patch(f"{URL}sinistres/{s['id']}/", {'statut': 'clos'}, format='json')
        self.assertEqual(Sinistre.objects.get(pk=s['id']).statut, 'conteste')

    def test_pieces_jointes(self):
        s = self.declarer().data
        r = self.client.post(f'{URL}pieces-jointes/', {'sinistre': s['id'], 'type_document': 'constat',
                             'fichier': SimpleUploadedFile('constat.pdf', b'%PDF-1.4', 'application/pdf')}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['nom'], 'constat.pdf')
        r = self.client.post(f'{URL}pieces-jointes/', {'sinistre': s['id'], 'type_document': 'photo',
                             'fichier': SimpleUploadedFile('x.exe', b'MZ', 'application/octet-stream')}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.client.get(f'{URL}sinistres/{s["id"]}/').data['pièces_jointes']), 1)
        self.client.force_authenticate(self.operateur_b)
        self.assertEqual(self.client.get(f'{URL}pieces-jointes/').data, [])

    def test_contrat_dates(self):
        r = self.client.post(f'{URL}contrats/', {'vehicule': str(self.v.id), 'assureur': self.assureur.id,
                                                 'numero_police': 'P2', 'type_contrat': 'rc', 'date_debut': '2026-06-01',
                                                 'date_fin': '2026-01-01', 'prime_annuelle': 1000}, format='json')
        self.assertIn('date_fin', r.data)

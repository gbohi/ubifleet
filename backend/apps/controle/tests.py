"""UbiFleet — Contrôle véhicule : cycle de la fiche."""
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.alertes.models import Alerte
from apps.core.testing import UtilisateursMixin
from apps.vehicules.models import Vehicule
from .models import ElementControle, FicheControle

URL = '/api/v1/controle/'


class FicheControleTests(UtilisateursMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.vehicule = Vehicule.objects.create(immatriculation='CT-1', agence=cls.agence_a, annee=2020)
        ElementControle.objects.all().delete()
        cls.freins = ElementControle.objects.create(nom='Freins', categorie='securite', obligatoire=True)
        cls.phares = ElementControle.objects.create(nom='Phares', categorie='eclairage')

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def creer(self, **extra):
        r = self.client.post(URL + 'fiches/', {'vehicule': str(self.vehicule.id), 'type_controle': 'depart',
                                               'date_heure': timezone.now().isoformat(), 'kilometrage': 1000, **extra},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def points(self, fid, pts):
        return self.client.post(URL + 'points/bulk_save/', {'fiche_id': fid, 'points': pts}, format='json')

    def test_reste_en_cours_jusqu_a_validation(self):
        fid = self.creer()
        fiche = FicheControle.objects.get(pk=fid)
        self.assertEqual((fiche.agence_id, fiche.statut_global), (self.agence_a.id, 'en_cours'))
        self.assertEqual(self.points(fid, [{'element': self.phares.id, 'statut': 'conforme'}]).status_code, 200)
        self.assertEqual(FicheControle.objects.get(pk=fid).statut_global, 'en_cours')   # pas encore validée
        # Point obligatoire manquant → validation refusée
        r = self.client.post(f'{URL}fiches/{fid}/valider/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Freins', r.data['detail'])
        self.points(fid, [{'element': self.freins.id, 'statut': 'conforme'}])
        r = self.client.post(f'{URL}fiches/{fid}/valider/')
        self.assertEqual(r.data['statut_global'], 'conforme')
        # Fiche figée
        self.assertEqual(self.points(fid, [{'element': self.phares.id, 'statut': 'na'}]).status_code, 400)
        self.assertEqual(self.client.patch(f'{URL}fiches/{fid}/', {'kilometrage': 5}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'{URL}fiches/{fid}/valider/').status_code, 400)

    def test_gravite_obligatoire_et_alerte(self):
        fid = self.creer()
        r = self.points(fid, [{'element': self.freins.id, 'statut': 'non_conforme'}])
        self.assertEqual(r.status_code, 400)          # gravité manquante
        self.points(fid, [{'element': self.freins.id, 'statut': 'conforme'},
                          {'element': self.phares.id, 'statut': 'non_conforme', 'gravite': 'majeur', 'remarque': 'Feu AV G'}])
        r = self.client.post(f'{URL}fiches/{fid}/valider/')
        self.assertEqual(r.data['statut_global'], 'partiel')
        a = Alerte.objects.get(type_alerte='controle_non_conforme')
        self.assertEqual((a.priorite, a.vehicule_id), ('haute', self.vehicule.id))
        self.assertIn('Feu AV G', a.message)

    def test_obligatoire_non_conforme(self):
        fid = self.creer()
        self.points(fid, [{'element': self.freins.id, 'statut': 'non_conforme', 'gravite': 'mineur'}])
        self.assertEqual(self.client.post(f'{URL}fiches/{fid}/valider/').data['statut_global'], 'non_conforme')
        self.assertFalse(Alerte.objects.filter(type_alerte='controle_non_conforme').exists())   # mineur : pas d'alerte

    def test_date_future_et_agence(self):
        r = self.client.post(URL + 'fiches/', {'vehicule': str(self.vehicule.id), 'type_controle': 'depart',
                                               'date_heure': (timezone.now() + timezone.timedelta(days=2)).isoformat(),
                                               'kilometrage': 1}, format='json')
        self.assertEqual(r.status_code, 400)
        fid = self.creer()
        self.client.force_authenticate(self.operateur_b)
        self.assertEqual(self.client.get(f'{URL}fiches/{fid}/').status_code, 404)
        lst = self.client.get(URL + 'fiches/').data['results']
        self.assertEqual(lst, [])

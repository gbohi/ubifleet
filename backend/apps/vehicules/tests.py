"""UbiFleet — Tests Véhicules (création et modification)."""

from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from apps.parametrage.models import MarqueVehicule, ModeleVehicule
from .models import Vehicule


class VehiculeSaisieTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.toyota = MarqueVehicule.objects.create(libelle='Toyota')
        cls.hilux = ModeleVehicule.objects.create(libelle='Hilux', marque=cls.toyota)
        cls.nissan = MarqueVehicule.objects.create(libelle='Nissan')
        cls.navara = ModeleVehicule.objects.create(libelle='Navara', marque=cls.nissan)

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def creer(self, **extra):
        data = {'immatriculation': '1001 AB 01', 'marque': self.toyota.id, 'modele': self.hilux.id, 'annee': 2022,
                'agence': str(self.agence_a.id), 'type_vehicule': 'pickup', 'type_carburant': 'diesel',
                'nombre_places': 5, 'kilometrage_actuel': 1000, **extra}
        return self.client.post('/api/v1/vehicules/', data, format='json')

    def test_creation(self):
        r = self.creer(immatriculation=' 1001  ab 01 ')
        self.assertEqual(r.status_code, 201, r.data)
        v = Vehicule.objects.get(pk=r.data['id'])
        self.assertEqual((v.immatriculation, v.kilometrage_initial, v.numero_chassis), ('1001 AB 01', 1000, None))

    def test_plusieurs_vehicules_sans_chassis(self):
        self.assertEqual(self.creer(numero_chassis='').status_code, 201)
        self.assertEqual(self.creer(immatriculation='1002 AB 01', numero_chassis='').status_code, 201)

    def test_immatriculation_equivalente_refusee(self):
        self.assertEqual(self.creer().status_code, 201)
        r = self.creer(immatriculation='1001AB-01')
        self.assertEqual(r.status_code, 400)
        self.assertIn('1001 AB 01', str(r.data['immatriculation']))

    def test_modele_de_la_marque(self):
        r = self.creer(modele=self.navara.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn('modele', r.data)

    def test_annee_bornee(self):
        self.assertEqual(self.creer(annee=1800).status_code, 400)

    def test_modification(self):
        v = self.creer().data['id']
        url = f'/api/v1/vehicules/{v}/'
        r = self.client.patch(url, {'couleur': 'Blanc', 'numero_chassis': '', 'chauffeur_attitré': None,
                                    'date_acquisition': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # Immatriculation : par le changement historisé ; archivage : par DELETE
        self.assertEqual(self.client.patch(url, {'immatriculation': '9999 ZZ 01'}, format='json').status_code, 400)
        self.client.patch(url, {'is_active': False}, format='json')
        self.assertTrue(Vehicule.objects.get(pk=v).is_active)

    def test_statistiques_de_tout_le_parc(self):
        from apps.parametrage.models import StatutVehicule
        en_service, _ = StatutVehicule.objects.get_or_create(code='en_service', defaults={'libelle': 'En service', 'couleur': 'green'})
        panne, _ = StatutVehicule.objects.get_or_create(code='en_panne', defaults={'libelle': 'En panne', 'couleur': 'red'})
        for i in range(25):
            self.creer(immatriculation=f'{2000 + i} CD 01')          # statut « En service » par défaut
        Vehicule.objects.filter(immatriculation='2000 CD 01').update(statut=panne)
        r = self.client.get('/api/v1/vehicules/stats/')
        par = {s['code']: s['nb'] for s in r.data['par_statut']}
        self.assertEqual((r.data['total'], par['en_service'], par['en_panne']), (25, 24, 1))
        # La liste est paginée, les statistiques non
        self.assertEqual(len(self.client.get('/api/v1/vehicules/', {'page_size': 10}).data['results']), 10)
        self.assertEqual(self.client.get('/api/v1/vehicules/', {'statut': 'en_panne'}).data['count'], 1)

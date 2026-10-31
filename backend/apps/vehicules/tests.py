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

    def test_types_de_vehicule_parametrables(self):
        from apps.parametrage.models import TypeVehicule
        self.client.force_authenticate(self.super_admin)
        r = self.client.post('/api/v1/parametrage/types-vehicule/', {'code': 'tricycle', 'libelle': 'Tricycle'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        v = self.creer(type_vehicule='tricycle').data
        self.assertEqual(v['type_vehicule'], 'tricycle')
        liste = self.client.get('/api/v1/vehicules/').data['results']
        self.assertEqual(liste[0]['type_vehicule_display'], 'Tricycle')
        # Utilisé : suppression refusée, code non modifiable ; désactivé : plus proposé
        t = TypeVehicule.objects.get(code='tricycle')
        self.assertEqual(self.client.delete(f'/api/v1/parametrage/types-vehicule/{t.id}/').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/parametrage/types-vehicule/{t.id}/', {'code': 'trike'},
                                           format='json').status_code, 400)
        self.client.patch(f'/api/v1/parametrage/types-vehicule/{t.id}/', {'actif': False}, format='json')
        self.assertEqual(self.creer(immatriculation='1002 AB 01', type_vehicule='tricycle').status_code, 400)
        self.assertEqual(self.creer(immatriculation='1003 AB 01', type_vehicule='inconnu').status_code, 400)

    def test_statut_change_par_l_historique(self):
        from apps.parametrage.models import StatutVehicule
        panne, _ = StatutVehicule.objects.get_or_create(code='en_panne', defaults={'libelle': 'En panne'})
        v = self.creer().data['id']
        self.assertEqual(self.client.patch(f'/api/v1/vehicules/{v}/', {'statut': panne.id}, format='json').status_code, 400)
        r = self.client.post(f'/api/v1/vehicules/{v}/historique-statuts/',
                             {'vehicule': v, 'nouveau_statut': panne.id, 'date_changement': '2026-10-01', 'motif': 'Moteur'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Vehicule.objects.get(pk=v).statut, panne)
        self.assertEqual(r.data['ancien_statut_libelle'], 'En service')

    def test_chauffeur_attitre_suit_les_affectations(self):
        from apps.chauffeurs.models import Chauffeur
        c1 = Chauffeur.objects.create(matricule='A1', nom='Un', prenom='C', agence=self.agence_a)
        c2 = Chauffeur.objects.create(matricule='A2', nom='Deux', prenom='C', agence=self.agence_a)
        v = self.creer(chauffeur_attitré=str(c1.id)).data['id']
        aff = self.client.get('/api/v1/vehicules/affectations/', {'vehicule': v}).data
        aff = aff.get('results', aff)
        self.assertEqual(len(aff), 1)                                     # affectation créée avec le véhicule
        # Chevauchement refusé ; après la fin de la 1re, la 2e devient le chauffeur attitré
        r = self.client.post('/api/v1/vehicules/affectations/', {'vehicule': v, 'chauffeur': str(c2.id),
                             'date_debut': '2026-01-01'}, format='json')
        self.assertEqual(r.status_code, 400)
        import datetime
        hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        self.client.patch(f"/api/v1/vehicules/affectations/{aff[0]['id']}/",
                          {'date_debut': hier, 'date_fin': hier}, format='json')
        r = self.client.post('/api/v1/vehicules/affectations/', {'vehicule': v, 'chauffeur': str(c2.id),
                             'date_debut': datetime.date.today().isoformat()}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Vehicule.objects.get(pk=v).chauffeur_attitré, c2)
        self.assertEqual(self.client.patch(f'/api/v1/vehicules/{v}/', {'chauffeur_attitré': str(c1.id)},
                                           format='json').status_code, 400)
        # Archivage : affectation terminée, statut « vendu » historisé
        self.client.force_authenticate(self.super_admin)
        self.client.delete(f'/api/v1/vehicules/{v}/')
        self.assertIsNone(Vehicule.objects.get(pk=v).chauffeur_attitré)

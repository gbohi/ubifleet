"""UbiFleet — Tests Entretien : cycle d'une intervention, statut du véhicule, synthèse."""

import datetime

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from apps.parametrage.models import StatutVehicule
from apps.vehicules.models import HistoriqueStatutVehicule, Vehicule
from .models import Intervention, TypeIntervention

URL = '/api/v1/entretien/interventions/'


class InterventionTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.en_service = StatutVehicule.objects.get(code='en_service')
        cls.v = Vehicule.objects.create(immatriculation='EN-1', agence=cls.agence_a, annee=2020,
                                        statut=cls.en_service, kilometrage_actuel=50000)
        cls.vidange = TypeIntervention.objects.create(nom='Vidange test', categorie='preventif')

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def creer(self, **extra):
        r = self.client.post(URL, {'vehicule': str(self.v.id), 'type_intervention': self.vidange.id,
                                   'date_planifiee': '2026-06-01', 'cout_estime': 40000, **extra}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_cycle_complet_et_statut_vehicule(self):
        i = self.creer()
        self.assertEqual(str(i['agence']), str(self.agence_a.id))      # agence du véhicule
        r = self.client.post(f"{URL}{i['id']}/demarrer/", {'date_debut': '2026-06-02'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['date_debut'], '2026-06-02')            # date saisie respectée
        self.v.refresh_from_db()
        self.assertEqual(self.v.statut.code, 'en_revision')
        self.assertTrue(HistoriqueStatutVehicule.objects.filter(vehicule=self.v, nouveau_statut__code='en_revision').exists())
        # Clôture : coût obligatoire, prochain km au-delà du compteur
        self.assertEqual(self.client.post(f"{URL}{i['id']}/terminer/", {}, format='json').status_code, 400)
        r = self.client.post(f"{URL}{i['id']}/terminer/", {'cout_reel': 45000, 'prochain_km': 40000}, format='json')
        self.assertIn('prochain_km', r.data)
        r = self.client.post(f"{URL}{i['id']}/terminer/", {'cout_reel': 45000, 'prochain_km': 60000,
                                                           'date_fin': '2026-06-03', 'rapport': 'RAS'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.v.refresh_from_db()
        self.assertEqual((self.v.statut.code, self.v.kilometrage_revision), ('en_service', 60000))
        # Terminée : ni re-clôture, ni changement de statut par le formulaire, ni suppression
        self.assertEqual(self.client.post(f"{URL}{i['id']}/terminer/", {'cout_reel': 1}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f"{URL}{i['id']}/", {'statut': 'planifie'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f"{URL}{i['id']}/").status_code, 400)
        # Le coût réel est reporté dans les dépenses
        from apps.budget.models import DepenseVehicule
        self.assertEqual(DepenseVehicule.objects.get(ref_objet_type='intervention').montant, 45000)

    def test_annulation_et_autre_intervention_en_cours(self):
        a, b = self.creer(), self.creer()
        self.client.post(f"{URL}{a['id']}/demarrer/", {}, format='json')
        self.client.post(f"{URL}{b['id']}/demarrer/", {}, format='json')
        self.assertEqual(self.client.post(f"{URL}{a['id']}/annuler/", {}, format='json').status_code, 400)  # motif
        r = self.client.post(f"{URL}{a['id']}/annuler/", {'motif': 'Doublon'}, format='json')
        self.assertEqual(r.data['statut'], 'annule')
        self.v.refresh_from_db()
        self.assertEqual(self.v.statut.code, 'en_revision')        # b toujours en cours
        self.client.post(f"{URL}{b['id']}/terminer/", {'cout_reel': 0}, format='json')
        self.v.refresh_from_db()
        self.assertEqual(self.v.statut.code, 'en_service')

    def test_controles_et_synthese(self):
        self.vidange.is_active = False
        self.vidange.save()
        r = self.client.post(URL, {'vehicule': str(self.v.id), 'type_intervention': self.vidange.id,
                                   'date_planifiee': '2026-06-01', 'cout_estime': 1}, format='json')
        self.assertEqual(r.status_code, 400)                         # type désactivé
        self.vidange.is_active = True
        self.vidange.save()
        self.assertEqual(self.client.post(URL, {'vehicule': str(self.v.id), 'type_intervention': self.vidange.id,
                                                'date_planifiee': '2026-06-01', 'cout_estime': -5},
                                          format='json').status_code, 400)
        self.assertEqual(self.client.post(URL, {'vehicule': str(self.v.id), 'type_intervention': self.vidange.id,
                                                'date_planifiee': '2026-06-01', 'statut': 'termine'},
                                          format='json').status_code, 400)
        hier = (timezone.localdate() - datetime.timedelta(days=3)).isoformat()
        self.creer(date_planifiee=hier, priorite='critique')
        s = self.client.get(f'{URL}synthese/').data
        self.assertEqual((s['total'], s['par_statut']['planifie'], s['urgentes'], s['en_retard']), (1, 1, 1, 1))
        # Autre agence : véhicule refusé
        self.client.force_authenticate(self.operateur_b)
        r = self.client.post(URL, {'vehicule': str(self.v.id), 'type_intervention': self.vidange.id,
                                   'date_planifiee': '2026-06-01'}, format='json')
        self.assertIn(r.status_code, (400, 403))

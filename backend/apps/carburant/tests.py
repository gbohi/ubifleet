"""UbiFleet — Tests de l'historique des prix du carburant."""

import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from apps.vehicules.models import Vehicule
from .models import PleinsCarburant, PrixCarburant


class PrixCarburantTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.diesel = Vehicule.objects.create(immatriculation='PX-1', agence=cls.agence_a, annee=2020,
                                             type_carburant='diesel')
        PrixCarburant.objects.create(type_carburant='diesel', prix=715, date_effet=datetime.date(2026, 6, 1))

    def test_prix_initial_repris(self):
        self.assertEqual(PrixCarburant.en_vigueur('essence', datetime.date(2026, 1, 1)).prix, 700)

    def test_prix_selon_la_date(self):
        self.assertEqual(PrixCarburant.en_vigueur('diesel', datetime.date(2026, 5, 31)).prix, 700)
        self.assertEqual(PrixCarburant.en_vigueur('diesel', datetime.date(2026, 6, 1)).prix, 715)
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.get(reverse('prix-carburant-en-vigueur'),
                               {'vehicule': str(self.diesel.id), 'date': '2026-07-15'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(float(resp.data['prix']), 715)

    def test_plein_sans_prix_recoit_le_prix_de_sa_date(self):
        plein = PleinsCarburant.objects.create(vehicule=self.diesel, date_plein=datetime.date(2026, 5, 10),
                                               volume_litres=40, kilometrage_releve=1000, agence=self.agence_a,
                                               montant_fcfa=0)
        self.assertEqual(plein.prix_litre, 700)

    def test_historique_fige(self):
        self.client.force_authenticate(self.responsable_flotte)
        passe = PrixCarburant.objects.get(type_carburant='diesel', prix=715)
        self.assertEqual(self.client.delete(reverse('prix-carburant-detail', args=[passe.id])).status_code, 403)
        demain = timezone.now().date() + datetime.timedelta(days=1)
        resp = self.client.post(reverse('prix-carburant-list'),
                                {'type_carburant': 'diesel', 'prix': 730, 'date_effet': demain.isoformat()}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.client.delete(reverse('prix-carburant-detail', args=[resp.data['id']])).status_code, 204)

    def test_saisie_reservee(self):
        self.client.force_authenticate(self.gestionnaire)
        resp = self.client.post(reverse('prix-carburant-list'),
                                {'type_carburant': 'diesel', 'prix': 1, 'date_effet': '2030-01-01'}, format='json')
        self.assertEqual(resp.status_code, 403)

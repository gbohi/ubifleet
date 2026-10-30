"""UbiFleet — Tests de l'historique des prix du carburant."""

import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.alertes.models import Alerte
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


class AnomalieConsommationTests(UtilisateursMixin, APITestCase):
    """Consommation plein à plein, référence = autres prises du véhicule,
    alerte « Consommation anormale » ouverte, mise à jour et clôturée."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.parametrage.models import Parametre, Tournee
        cls.vehicule = Vehicule.objects.create(immatriculation='AN-1', agence=cls.agence_a, annee=2020,
                                               type_carburant='diesel', kilometrage_actuel=10000,
                                               kilometrage_initial=10000)
        cls.tournee = Tournee.objects.create(code='AN-T', libelle='Tournée AN', agence=cls.agence_a)
        Parametre.objects.update_or_create(cle='fenetre_saisie_carburant_jours',
                                           defaults={'valeur': '0', 'type_valeur': 'int'})
        cls.debut = timezone.localdate() - datetime.timedelta(days=30)

    def prise(self, n, km, litres):
        """Prise au jour `debut + n`, via l'API (recalcul et alerte compris)."""
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post('/api/v1/carburant/pleins/', {
            'vehicule': str(self.vehicule.id), 'date_plein': (self.debut + datetime.timedelta(days=n)).isoformat(),
            'heure_plein': '08:00', 'tournee': self.tournee.id, 'volume_litres': litres,
            'montant_fcfa': 28000, 'kilometrage_releve': km,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return PleinsCarburant.objects.get(pk=resp.data['id'])

    def historique_normal(self):
        """Référence : 4 intervalles de 500 km à 10 L/100 km."""
        self.prise(0, 10000, 50)
        for i in range(1, 5):
            self.prise(i, 10000 + 500 * i, 50)

    def alertes(self):
        return Alerte.objects.filter(type_alerte=Alerte.TypeAlerte.CONSO_ANORMALE)

    def test_consommation_plein_a_plein(self):
        self.prise(0, 10000, 50)
        p = self.prise(1, 10400, 36)
        self.assertEqual(p.kilometrage_depart, 10000)
        self.assertEqual(float(p.consommation_calculee), 9.0)

    def test_historique_insuffisant(self):
        # Moins de 3 autres prises avec consommation : pas de jugement
        self.prise(0, 10000, 50)
        self.prise(1, 10500, 50)
        self.prise(2, 11000, 50)
        p = self.prise(3, 11500, 150)
        self.assertEqual(p.statut_validation, 'valide')
        self.assertFalse(self.alertes().exists())

    def test_seuil_atteint_sans_anomalie(self):
        # 13 L/100 km pour une moyenne de 10 : +30 % = seuil, pas d'anomalie
        self.historique_normal()
        p = self.prise(5, 12500, 65)
        self.assertEqual(p.statut_validation, 'valide')

    def test_reference_hors_prise_controlee(self):
        # 13,6 L/100 km : anomalie. Inclure la prise dans la moyenne
        # (10,72 → seuil 13,94) l'aurait masquée.
        self.historique_normal()
        p = self.prise(5, 12500, 68)
        self.assertEqual(p.statut_validation, 'anomalie')
        self.assertIn('13,60 L/100 km', p.motif_anomalie)
        self.assertIn('10,', p.motif_anomalie)

    def test_alerte_ouverte_puis_cloturee_apres_correction(self):
        self.historique_normal()
        p = self.prise(5, 12500, 90)
        alerte = self.alertes().get()
        self.assertEqual(alerte.plein, p)
        self.assertEqual(alerte.statut, Alerte.Statut.ACTIVE)
        self.assertEqual(alerte.agence, self.agence_a)
        self.assertEqual(alerte.vehicule, self.vehicule)
        self.assertIn('AN-1', alerte.titre)
        self.assertIn('90,00 L pour 500 km', alerte.message)
        # Volume corrigé : la consommation redevient normale, l'alerte est clôturée
        self.client.force_authenticate(self.super_admin)
        resp = self.client.patch(f'/api/v1/carburant/pleins/{p.id}/', {'volume_litres': 50}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        alerte.refresh_from_db()
        self.assertEqual(alerte.statut, Alerte.Statut.TRAITEE)
        self.assertIn('automatiquement', alerte.notes_traitement)
        p.refresh_from_db()
        self.assertEqual(p.statut_validation, 'valide')

    def test_alerte_traitee_non_rouverte_sans_changement(self):
        self.historique_normal()
        p = self.prise(5, 12500, 90)
        alerte = self.alertes().get()
        alerte.statut = Alerte.Statut.TRAITEE
        alerte.save()
        # Une prise antérieure corrigée sans effet sur cette consommation : rien ne bouge
        premiere = PleinsCarburant.objects.filter(vehicule=self.vehicule).order_by('date_plein').first()
        self.client.force_authenticate(self.super_admin)
        resp = self.client.patch(f'/api/v1/carburant/pleins/{premiere.id}/', {'bon_carburant': 'B1'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        alerte.refresh_from_db()
        self.assertEqual(alerte.statut, Alerte.Statut.TRAITEE)
        # La prise elle-même corrigée, toujours anormale : alerte rouverte et mise à jour
        resp = self.client.patch(f'/api/v1/carburant/pleins/{p.id}/', {'volume_litres': 95}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        alerte.refresh_from_db()
        self.assertEqual(alerte.statut, Alerte.Statut.ACTIVE)
        self.assertIn('95,00 L', alerte.message)
        self.assertEqual(self.alertes().count(), 1)

    def test_suppression_de_la_prise(self):
        self.historique_normal()
        p = self.prise(5, 12500, 90)
        self.assertTrue(self.alertes().exists())
        self.client.force_authenticate(self.super_admin)
        resp = self.client.delete(f'/api/v1/carburant/pleins/{p.id}/', {'motif': 'Doublon'}, format='json')
        self.assertIn(resp.status_code, (200, 204), getattr(resp, 'data', None))
        self.assertFalse(self.alertes().exists())

    def test_alerte_visible_par_l_agence(self):
        self.historique_normal()
        self.prise(5, 12500, 90)
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.get('/api/v1/alertes/', {'type_alerte': 'conso_anormale'})
        self.assertEqual(resp.status_code, 200)
        res = resp.data.get('results', resp.data)
        self.assertEqual(len(res), 1)
        self.assertIsNotNone(res[0]['plein'])
        self.client.force_authenticate(self.operateur_b)
        resp = self.client.get('/api/v1/alertes/', {'type_alerte': 'conso_anormale'})
        self.assertEqual(len(resp.data.get('results', resp.data)), 0)

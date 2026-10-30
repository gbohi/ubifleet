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
            'heure_plein': '08:00', 'type_mouvement': 'tournee', 'tournee': self.tournee.id, 'volume_litres': litres,
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


class TourneesEffectueesTests(UtilisateursMixin, APITestCase):
    """Tournée ouverte par sa 1re prise, prises rattachées, clôture avec KM
    retour, droits configurables, suivi tournées / hors tournée."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.parametrage.models import Parametre, Tournee
        cls.vehicule = Vehicule.objects.create(immatriculation='TE-1', agence=cls.agence_a, annee=2020,
                                               type_carburant='diesel', kilometrage_actuel=10000,
                                               kilometrage_initial=10000, conso_theorique_origine=10)
        cls.a01 = Tournee.objects.create(code='A01', libelle='Tournée A01', agence=cls.agence_a,
                                         dotation=30, km_theorique=250)
        Parametre.objects.update_or_create(cle='fenetre_saisie_carburant_jours',
                                           defaults={'valeur': '0', 'type_valeur': 'int'})
        Parametre.objects.update_or_create(cle='fenetre_saisie_releves_jours',
                                           defaults={'valeur': '0', 'type_valeur': 'int'})
        cls.j0 = timezone.localdate() - datetime.timedelta(days=20)

    def setUp(self):
        from apps.accounts.permission_cache import invalidate
        invalidate()

    def prise(self, jour, heure, km, litres, type_mvt='tournee', tournee=True, user=None, **extra):
        self.client.force_authenticate(user or self.operateur)
        data = {'vehicule': str(self.vehicule.id), 'date_plein': (self.j0 + datetime.timedelta(days=jour)).isoformat(),
                'heure_plein': heure, 'type_mouvement': type_mvt, 'volume_litres': litres,
                'montant_fcfa': litres * 700, 'kilometrage_releve': km, **extra}
        if tournee:
            data['tournee'] = self.a01.id
        return self.client.post('/api/v1/carburant/pleins/', data, format='json')

    def suivi(self, user=None):
        self.client.force_authenticate(user or self.operateur)
        return self.client.get('/api/v1/carburant/tournees/').data

    def test_exemple_a01_deux_realisations(self):
        # 1re réalisation : 3 prises sur deux jours, clôture à la dernière
        self.assertEqual(self.prise(0, '18:00', 10000, 10).status_code, 201)
        r = self.prise(0, '20:00', 10100, 12, tournee=False)   # tournée en cours : déduite
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['tournee_code'], 'A01')
        r = self.prise(1, '10:00', 10240, 5, cloturer_tournee=True, commentaire_tournee='RAS')
        self.assertEqual(r.status_code, 201, r.data)
        # 2e réalisation, clôturée plus tard avec un KM retour
        self.prise(3, '18:00', 10300, 10)
        self.prise(3, '21:00', 10400, 12, tournee=False)
        lignes = self.suivi()['resultats']
        self.assertEqual(len(lignes), 2)
        l1, l2 = lignes
        self.assertEqual((l1['statut'], l1['nb_prises'], l1['vol_reel']), ('cloturee', 3, 27.0))
        self.assertEqual((l1['km_depart'], l1['km_retour'], l1['km_parcouru']), (10000, 10240, 240))
        self.assertEqual(l1['vol_theorique'], 30)
        self.assertEqual(l1['ecart_dotation'], -3.0)
        self.assertEqual(l1['conso_reel'], 11.25)
        self.assertEqual(l1['conso_theorique'], 12.0)
        self.assertEqual(l1['ecart_conso'], -0.8)
        self.assertEqual(l1['commentaire'], 'RAS')
        self.assertEqual(l2['statut'], 'en_cours')
        self.assertNotEqual(l1['numero'], l2['numero'])
        self.client.force_authenticate(self.operateur)
        r = self.client.post(f"/api/v1/carburant/tournees/{l2['id']}/cloturer/",
                             {'km_retour': 10350}, format='json')
        self.assertEqual(r.status_code, 400)                    # < dernière prise
        r = self.client.post(f"/api/v1/carburant/tournees/{l2['id']}/cloturer/",
                             {'km_retour': 10560, 'date_fin': (self.j0 + datetime.timedelta(days=4)).isoformat(),
                              'heure_fin': '09:00'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['km_parcouru'], r.data['vol_reel']), (260, 22.0))
        # Relevé de retour créé : compteur à jour
        self.vehicule.refresh_from_db()
        self.assertEqual(self.vehicule.kilometrage_actuel, 10560)

    def test_prise_d_un_autre_type_pendant_une_tournee(self):
        self.prise(0, '08:00', 10000, 20)
        r = self.prise(0, '12:00', 10100, 10, type_mvt='course', tournee=False)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Clôturez', str(r.data['type_mouvement']))

    def test_hors_tournee_estimation(self):
        self.prise(0, '08:00', 10000, 20, type_mvt='course', tournee=False)
        r = self.prise(1, '08:00', 10200, 25, type_mvt='ramassage', tournee=False)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['tournee'])
        self.client.force_authenticate(self.operateur)
        lignes = self.client.get('/api/v1/carburant/tournees/hors_tournee/').data['resultats']
        l = lignes[-1]
        self.assertEqual((l['type_display'], l['km_parcouru'], l['vol_estime'], l['ecart']), ('Ramassage', 200, 20.0, 5.0))
        self.assertEqual(l['source_reference'], 'reference')
        syn = self.client.get('/api/v1/carburant/tournees/synthese/').data
        self.assertEqual((syn['vol_hors'], syn['part_hors_pct']), (45.0, 100.0))

    def test_tournee_a_une_seule_prise(self):
        r = self.prise(0, '08:00', 10000, 25, cloturer_tournee=True)
        self.assertEqual(r.status_code, 201, r.data)
        l = self.suivi()['resultats'][0]
        self.assertEqual((l['statut'], l['nb_prises'], l['km_parcouru']), ('cloturee', 1, None))

    def test_droit_de_cloturer_configurable(self):
        from apps.accounts.models import PermissionRole
        PermissionRole.objects.create(role=self.roles['operateur'], module='carburant',
                                      action='cloturer_tournee', autorise=False)
        r = self.prise(0, '08:00', 10000, 25, cloturer_tournee=True)
        self.assertEqual(r.status_code, 403)
        self.prise(0, '08:00', 10000, 25)
        data = self.suivi()
        self.assertFalse(data['droits']['cloturer'])
        r = self.client.post(f"/api/v1/carburant/tournees/{data['resultats'][0]['id']}/cloturer/", {}, format='json')
        self.assertEqual(r.status_code, 403)
        # Le gestionnaire garde le droit par défaut
        self.client.force_authenticate(self.gestionnaire)
        r = self.client.post(f"/api/v1/carburant/tournees/{data['resultats'][0]['id']}/cloturer/", {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_rouvrir_et_annuler(self):
        self.prise(0, '08:00', 10000, 25)
        te = self.suivi()['resultats'][0]
        self.client.force_authenticate(self.operateur)
        self.client.post(f"/api/v1/carburant/tournees/{te['id']}/cloturer/",
                         {'km_retour': 10300, 'date_fin': (self.j0 + datetime.timedelta(days=1)).isoformat()},
                         format='json')
        r = self.client.post(f"/api/v1/carburant/tournees/{te['id']}/rouvrir/", {}, format='json')
        self.assertEqual(r.status_code, 403)                    # opérateur : pas le droit par défaut
        self.client.force_authenticate(self.responsable_flotte)
        r = self.client.post(f"/api/v1/carburant/tournees/{te['id']}/rouvrir/", {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'en_cours')
        self.vehicule.refresh_from_db()
        self.assertEqual(self.vehicule.kilometrage_actuel, 10000)   # relevé de retour supprimé
        r = self.client.post(f"/api/v1/carburant/tournees/{te['id']}/annuler/",
                             {'type_mouvement': 'course', 'motif': 'Ouverte par erreur'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.suivi()['count'], 0)
        p = PleinsCarburant.objects.get(vehicule=self.vehicule)
        self.assertEqual((p.type_mouvement, p.tournee_id, p.tournee_effectuee_id), ('course', None, None))

    def test_suppression_de_la_derniere_prise(self):
        r = self.prise(0, '08:00', 10000, 25)
        self.client.force_authenticate(self.super_admin)
        self.client.delete(f"/api/v1/carburant/pleins/{r.data['id']}/", {'motif': 'Doublon'}, format='json')
        self.assertEqual(self.suivi()['count'], 0)

    def test_dotation_figee_a_l_ouverture(self):
        self.prise(0, '08:00', 10000, 25)
        self.a01.dotation = 50
        self.a01.save()
        self.assertEqual(self.suivi()['resultats'][0]['vol_theorique'], 30)

    def test_alerte_tournee_non_cloturee(self):
        from apps.alertes.tasks import run_all_checks_sync
        self.prise(0, '08:00', 10000, 25)
        run_all_checks_sync()
        a = Alerte.objects.get(type_alerte='tournee_ouverte')
        self.assertIn('TE-1', a.titre)
        te = self.suivi()['resultats'][0]
        self.client.force_authenticate(self.operateur)
        self.client.post(f"/api/v1/carburant/tournees/{te['id']}/cloturer/", {}, format='json')
        run_all_checks_sync()
        a.refresh_from_db()
        self.assertEqual(a.statut, 'traitee')

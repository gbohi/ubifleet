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

    def _evaluer(self):
        from .anomalies import evaluer, prises_du_vehicule
        prises = prises_du_vehicule(self.vehicule)
        return prises, evaluer(prises)

    def test_compteur_errone_ne_fausse_pas_la_reference(self):
        # Donnée existante (import, saisie ancienne) : un compteur à +100 000 km au milieu
        # de l'historique est signalé, n'entre pas dans la référence, et la prise suivante
        # se calcule depuis la dernière prise cohérente.
        self.historique_normal()
        derniere = self.prise(5, 12500, 68)                  # 13,6 L/100 km pour 10 de moyenne
        prises, ev = self._evaluer()
        PleinsCarburant.objects.filter(pk=prises[3].pk).update(kilometrage_releve=111500)
        prises, ev = self._evaluer()
        self.assertIn('kilométrage probablement erroné', ev[prises[3].pk].motif)
        self.assertTrue(ev[prises[3].pk].km_incoherent)
        self.assertEqual(ev[prises[4].pk].depart, 11000)      # depuis la prise 2 (cohérente)
        self.assertEqual(ev[derniere.pk].reference, 10.0)      # référence non faussée
        self.assertTrue(ev[derniere.pk].motif)                 # l'anomalie réelle reste détectée

    def test_compteur_inferieur_signale(self):
        self.historique_normal()
        prises, _ = self._evaluer()
        PleinsCarburant.objects.filter(pk=prises[4].pk).update(kilometrage_releve=9000)
        prises, ev = self._evaluer()
        self.assertIn('inférieur à celui de la prise précédente', ev[prises[4].pk].motif)
        self.assertIsNone(ev[prises[4].pk].conso)

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


class AnalysesCarburantTests(UtilisateursMixin, APITestCase):
    """Onglets Consommation, Évolution par agence et Rapprochement Total."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.chauffeurs.models import Chauffeur
        cls.agence_a.numero_client_total = '132'
        cls.agence_a.save()
        cls.v = Vehicule.objects.create(immatriculation='56317 WW 01', agence=cls.agence_a, annee=2020,
                                        type_carburant='diesel', kilometrage_actuel=10000,
                                        kilometrage_initial=10000, conso_theorique_origine=10)
        cls.ch = Chauffeur.objects.create(matricule='C1', nom='KONE', prenom='Moussa', agence=cls.agence_a,
                                          numero_chauffeur_total='0005')
        cls.d = datetime.date(2026, 5, 4)

    def prise(self, jour, heure, km, litres, type_mvt='course'):
        p = PleinsCarburant.objects.create(
            vehicule=self.v, agence=self.agence_a, chauffeur=self.ch, type_mouvement=type_mvt,
            date_plein=self.d + datetime.timedelta(days=jour), heure_plein=datetime.time(*heure),
            volume_litres=litres, montant_fcfa=litres * 675, prix_litre=675, kilometrage_releve=km)
        from apps.vehicules.kilometrage import recalculer_consommations
        recalculer_consommations(self.v, self.d)
        return p

    def transaction(self, jour, heure, litres, km, code, plaque='56317WW-CI', chauffeur='0005', carte='111'):
        from apps.total_import.models import ImportTotal, TransactionCarburant
        imp = ImportTotal.objects.get_or_create(fichier_nom='t.csv')[0]
        return TransactionCarburant.objects.create(
            import_source=imp, numero_client='132', immatriculation=plaque, numero_chauffeur=chauffeur,
            numero_moyen_paiement=f'="{carte}"', date_transaction=self.d + datetime.timedelta(days=jour),
            heure_transaction=datetime.time(*heure), volume=litres, montant=litres * 675,
            kilometrage_actuel=km, numero_ticket=str(code), code_autorisation=str(code))

    def get(self, action, **params):
        self.client.force_authenticate(self.responsable_flotte)
        return self.client.get(f'/api/v1/carburant/pleins/{action}/',
                               {'date_debut': '2026-05-01', 'date_fin': '2026-05-31', **params})

    def test_consommation_plein_a_plein(self):
        self.prise(0, (8, 0), 10000, 50)
        self.prise(1, (8, 0), 10500, 55, 'tournee')
        self.prise(2, (8, 0), 11000, 65)
        r = self.get('consommation')
        self.assertEqual(r.status_code, 200, r.data)
        l = r.data['resultats'][0]
        self.assertEqual((l['nb_prises'], l['km_parcourus'], l['litres']), (3, 1000, 170.0))
        self.assertEqual(l['conso_moyenne'], 12.0)            # (55 + 65) / 1000 km
        self.assertEqual((l['conso_reference'], l['ecart_pct']), (10.0, 20.0))
        self.assertEqual(l['derniere_conso'], 13.0)
        self.assertEqual(l['part_hors_tournee'], 67.6)
        # Filtre par type : seuls les intervalles des prises de ce type
        l = self.get('consommation', type_mouvement='tournee').data['resultats'][0]
        self.assertEqual((l['km_parcourus'], l['conso_moyenne']), (500, 11.0))

    def test_historique_insuffisant(self):
        self.prise(0, (8, 0), 10000, 50)
        l = self.get('consommation').data['resultats'][0]
        self.assertTrue(l['historique_insuffisant'])
        self.assertIsNone(l['conso_moyenne'])

    def test_evolution_mois_vides_et_decoupage(self):
        self.prise(0, (8, 0), 10000, 50)
        self.prise(1, (8, 0), 10500, 55, 'tournee')
        self.client.force_authenticate(self.responsable_flotte)
        r = self.client.get('/api/v1/carburant/pleins/evolution_agences/',
                            {'date_debut': '2026-03-01', 'date_fin': '2026-05-31'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['mois'], ['2026-03', '2026-04', '2026-05'])
        pts = r.data['agences'][0]['points']
        self.assertEqual([p['volume'] for p in pts], [0, 0, 105.0])
        self.assertEqual((pts[2]['volume_tournee'], pts[2]['volume_hors'], pts[2]['nb']), (55.0, 50.0, 2))
        self.assertEqual(pts[2]['conso'], 11.0)

    def test_rapprochement(self):
        self.prise(0, (8, 0), 10000, 50)          # ↔ transaction 8h20 : rapprochée
        self.prise(1, (9, 0), 10500, 55)          # ↔ transaction 50 L : écart de volume
        self.prise(3, (10, 0), 11000, 40)         # aucune transaction : payée autrement ?
        self.transaction(0, (8, 20), 50, 10000, 1)
        self.transaction(1, (9, 30), 50, 10500, 2)
        self.transaction(2, (7, 0), 45, 10800, 3)                 # sans prise déclarée
        self.transaction(2, (7, 5), -45, 10800, -3)               # … annulée (timeout)
        self.transaction(2, (18, 0), 30, 10900, 4)                # sans prise déclarée
        self.transaction(1, (12, 0), 40, 5000, 5, plaque='99999 XX 01', carte='999')   # plaque inconnue
        r = self.get('rapprochement_total')
        self.assertEqual(r.status_code, 200, r.data)
        statuts = sorted(l['statut'] for l in r.data['lignes'])
        self.assertEqual(statuts, ['ecart', 'prise_sans_transaction', 'rapproche', 'transaction_sans_prise'])
        s = r.data['synthese'][0]
        self.assertEqual((s['litres_declares'], s['litres_factures'], s['ecart_litres']), (145.0, 130.0, 15.0))
        self.assertEqual(r.data['immatriculations_inconnues'][0]['immatriculation'], '99999 XX 01')
        ecart = next(l for l in r.data['lignes'] if l['statut'] == 'ecart')
        self.assertEqual(ecart['ecart_volume_pct'], 10.0)
        self.assertFalse(ecart['chauffeur_different'])

    def test_carte_prioritaire_sur_la_plaque(self):
        self.v.numero_carte_carburant = '7903 1800'
        self.v.save()
        self.prise(0, (8, 0), 10000, 50)
        self.transaction(0, (8, 10), 50, 10000, 1, plaque='36930', carte='79031800')
        r = self.get('rapprochement_total')
        self.assertEqual([l['statut'] for l in r.data['lignes']], ['rapproche'])

    def test_tolerance_parametrable(self):
        from apps.parametrage.models import Parametre
        self.prise(0, (8, 0), 10000, 50)
        self.transaction(0, (16, 0), 50, 10000, 1)          # 8 h d'écart > 6 h par défaut
        self.assertEqual(self.get('rapprochement_total').data['totaux']['nb_rapproches'], 0)
        Parametre.objects.update_or_create(cle='rapprochement_tolerance_heures',
                                           defaults={'valeur': '10', 'type_valeur': 'int'})
        self.assertEqual(self.get('rapprochement_total').data['totaux']['nb_rapproches'], 1)

    def test_normalisation_des_plaques(self):
        from .analyses import normaliser_immat
        self.assertEqual(normaliser_immat('56317WW-CI'), normaliser_immat('56317 WW 01'))
        self.assertEqual(normaliser_immat('36929 WW'), normaliser_immat('36929 WW 01'))
        self.assertEqual(normaliser_immat('AA-623-YG-01'), 'AA623YG')

    def test_consommation_facturee(self):
        from apps.vehicules.models import ReleveKilometrage
        self.prise(0, (8, 0), 10000, 50)
        self.prise(2, (8, 0), 11000, 50)
        # Relevé intermédiaire : le compteur d'une transaction sans prise est interpolé
        ReleveKilometrage.objects.create(vehicule=self.v, kilometrage=10400, date_releve=self.d + datetime.timedelta(days=1),
                                         heure_releve=datetime.time(8, 0))
        self.transaction(0, (8, 0), 50, 0, 1)            # kilométrage pompe nul : ignoré, compteur UbiFleet utilisé
        self.transaction(1, (20, 0), 60, 0, 2)           # 20 h : entre 10 400 (8 h) et 11 000 (le lendemain 8 h)
        self.transaction(2, (8, 0), 55, 0, 3)
        self.transaction(2, (8, 5), -55, 0, -3)          # annulée
        self.transaction(2, (9, 0), 55, 0, 4)
        self.client.force_authenticate(self.responsable_flotte)
        r = self.client.get('/api/v1/vehicules/consommation-km/', {'date_debut': '2026-05-01', 'date_fin': '2026-05-31'})
        self.assertEqual(r.status_code, 200, r.data)
        l = r.data['resultats'][0]
        self.assertEqual((l['nb_transactions'], l['litres_factures']), (3, 165.0))
        # km : 10 000 (1re transaction) → 11 000 (dernière, 9 h : après la dernière saisie) ; litres hors 1re : 115
        self.assertEqual((l['km_debut'], l['km_fin'], l['km_parcourus']), (10000, 11000, 1000))
        self.assertEqual(l['conso_facturee'], 11.5)
        self.assertEqual((l['conso_declaree'], l['conso_reference'], l['ecart_reference_pct']), (5.0, 10.0, 15.0))
        self.assertEqual(l['ecart_declaree_pct'], 130.0)

    def test_tableau_de_bord_conso_ponderee(self):
        # 100 km à 30 L/100 puis 900 km à 10 L/100 : moyenne pondérée 12, pas (30 + 10) / 2 = 20
        self.prise(0, (8, 0), 10000, 40)
        self.prise(1, (8, 0), 10100, 30)
        self.prise(2, (8, 0), 11000, 90)
        self.client.force_authenticate(self.responsable_flotte)
        r = self.client.get('/api/v1/rapports/dashboard/', {'mois': 5, 'annee': 2026})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['carburant']['conso_moy'], 12.0)
        self.assertEqual(r.data['top_ecart_conso'][0]['ecart_pct'], 20.0)       # référence 10
        r = self.client.get('/api/v1/rapports/carburant/', {'mois': 5, 'annee': 2026})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['global']['conso_moy'], 12.0)
        self.assertEqual((r.data['par_vehicule'][0]['conso_moy'], r.data['par_vehicule'][0]['ecart_pct']), (12.0, 20.0))

    def test_utilisation_du_parc(self):
        from apps.parametrage.models import Parametre
        from apps.vehicules.models import ReleveKilometrage
        Parametre.objects.update_or_create(cle='utilisation_saut_km_jour', defaults={'valeur': '500', 'type_valeur': 'int'})
        self.v.kilometrage_revision = 12000
        self.v.save()
        self.prise(0, (8, 0), 10000, 50)                                   # 4 mai
        ReleveKilometrage.objects.create(vehicule=self.v, kilometrage=10300, date_releve=self.d + datetime.timedelta(days=1),
                                         heure_releve=datetime.time(8))     # 5 mai : +300 km/jour
        self.prise(2, (8, 0), 11100, 50)                                   # 6 mai : +800 km en 1 jour → saut
        self.client.force_authenticate(self.responsable_flotte)
        r = self.client.get('/api/v1/vehicules/utilisation/', {'date_debut': '2026-05-01', 'date_fin': '2026-05-31'})
        self.assertEqual(r.status_code, 200, r.data)
        l = next(x for x in r.data['resultats'] if x['immatriculation'] == '56317 WW 01')
        self.assertEqual((l['km_debut'], l['km_fin'], l['km_parcourus']), (10000, 11100, 1100))
        self.assertEqual((l['jours_utilisation'], l['km_par_jour_roule'], l['nb_saisies']), (2, 550, 3))
        self.assertEqual(l['nb_sauts'], 1)
        self.assertEqual(l['sauts'][0]['km'], 800)
        self.assertEqual(l['jours_sans_saisie'], 25)                       # 6 → 31 mai
        self.assertTrue(l['sans_saisie_recente'])
        self.assertEqual(l['km_avant_revision'], 12000 - self.v.__class__.objects.get(pk=self.v.pk).kilometrage_actuel)
        r = self.client.get('/api/v1/vehicules/utilisation/courbe/',
                            {'vehicule': str(self.v.id), 'date_debut': '2026-05-01', 'date_fin': '2026-05-31'})
        self.assertEqual([p['km'] for p in r.data['points']], [10000, 10300, 11100])

    def test_cout_km_chauffeurs_fiches(self):
        self.prise(0, (8, 0), 10000, 50)
        self.prise(1, (8, 0), 10500, 55)
        self.prise(2, (8, 0), 11000, 65)
        self.client.force_authenticate(self.responsable_flotte)
        # Coût carburant au km : (55 + 65) × 675 / 1000 km
        l = self.get('consommation').data['resultats'][0]
        self.assertEqual(l['cout_km'], 81.0)
        # Classement des chauffeurs : conso 12 vs référence 10 → +20 %
        r = self.get('chauffeurs')
        self.assertEqual(r.status_code, 200, r.data)
        c = r.data['resultats'][0]
        self.assertEqual((c['chauffeur'], c['conso_moyenne'], c['conso_reference'], c['ecart_pct']),
                         ('C1 — Moussa KONE', 12.0, 10.0, 20.0))
        # Utilisation du parc : coût total au km (dépenses carburant reportées depuis les prises)
        u = self.client.get('/api/v1/vehicules/utilisation/', {'date_debut': '2026-05-01', 'date_fin': '2026-05-31'}).data
        v = next(x for x in u['resultats'] if x['immatriculation'] == '56317 WW 01')
        self.assertEqual((v['km_parcourus'], v['depenses'], v['cout_km']), (1000, 114750, 114.8))
        self.assertEqual(u['par_agence'][0]['cout_km'], 114.8)

    def test_compteur_interpole(self):
        from .analyses import compteur_a
        t = lambda h: datetime.datetime(2026, 5, 1, h)
        saisies = [(t(8), 1000), (t(18), 1100)]
        self.assertEqual(compteur_a(saisies, t(13)), 1050)
        self.assertEqual(compteur_a(saisies, t(20)), 1100)
        self.assertEqual(compteur_a(saisies, t(6)), 1000)
        self.assertIsNone(compteur_a([], t(6)))


class DepensesDesPrisesTests(UtilisateursMixin, APITestCase):
    """Chaque prise de carburant a sa dépense « Carburant » dans le budget."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.v = Vehicule.objects.create(immatriculation='DP-1', agence=cls.agence_a, annee=2020,
                                        type_carburant='diesel', kilometrage_actuel=1000, kilometrage_initial=1000)

    def depenses(self):
        from apps.budget.models import DepenseVehicule
        return DepenseVehicule.objects.filter(ref_objet_type='prise_carburant')

    def test_creee_modifiee_supprimee_avec_la_prise(self):
        p = PleinsCarburant.objects.create(vehicule=self.v, agence=self.agence_a, date_plein=datetime.date(2026, 5, 4),
                                           heure_plein=datetime.time(8), volume_litres=40, montant_fcfa=27000,
                                           kilometrage_releve=1200, bon_carburant='B-12')
        d = self.depenses().get()
        self.assertEqual((d.categorie, float(d.montant), d.vehicule, d.agence, d.numero_facture),
                         ('carburant', 27000.0, self.v, self.agence_a, 'B-12'))
        p.montant_fcfa = 28000
        p.save()
        self.assertEqual(float(self.depenses().get().montant), 28000.0)
        p.delete()
        self.assertFalse(self.depenses().exists())

    def test_realise_du_budget(self):
        from apps.budget.models import BudgetAnnuel
        PleinsCarburant.objects.create(vehicule=self.v, agence=self.agence_a, date_plein=datetime.date(2026, 5, 4),
                                       heure_plein=datetime.time(8), volume_litres=40, montant_fcfa=27000,
                                       kilometrage_releve=1200)
        b = BudgetAnnuel.objects.create(agence=self.agence_a, annee=2026, budget_carburant=1000000)
        self.client.force_authenticate(self.responsable_flotte)
        r = self.client.get(f'/api/v1/budget/budgets/{b.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['realise'].get('carburant'), 27000.0)

    def test_depense_automatique_non_modifiable(self):
        PleinsCarburant.objects.create(vehicule=self.v, agence=self.agence_a, date_plein=datetime.date(2026, 5, 4),
                                       heure_plein=datetime.time(8), volume_litres=40, montant_fcfa=27000,
                                       kilometrage_releve=1200)
        d = self.depenses().get()
        self.client.force_authenticate(self.super_admin)
        r = self.client.patch(f'/api/v1/budget/depenses/{d.id}/', {'montant': 1}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.delete(f'/api/v1/budget/depenses/{d.id}/').status_code, 400)
        self.assertTrue(self.client.get(f'/api/v1/budget/depenses/{d.id}/').data['automatique'])

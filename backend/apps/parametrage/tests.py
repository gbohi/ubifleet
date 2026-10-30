"""UbiFleet — Tests des échéances unifiées (seuils, État du parc, alertes)."""

import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.alertes.models import Alerte
from apps.alertes.tasks import run_all_checks_sync
from apps.core.testing import UtilisateursMixin
from apps.vehicules.models import DocumentVehicule, TypeDocumentVehicule, Vehicule
from .echeances import ATTENTION, DEPASSE, NC, OK, URGENT, niveau, seuils
from .models import Parametre


def regler(code, attention, urgent):
    for n, v in (('attention', attention), ('urgent', urgent)):
        Parametre.objects.update_or_create(cle=f'echeance_{code}_{n}',
                                           defaults={'valeur': str(v), 'type_valeur': 'int'})


class NiveauTests(APITestCase):
    def test_niveaux(self):
        self.assertEqual(niveau(None, 30, 7), NC)
        self.assertEqual(niveau(0, 30, 7), DEPASSE)
        self.assertEqual(niveau(-3, 30, 7), DEPASSE)
        self.assertEqual(niveau(7, 30, 7), URGENT)
        self.assertEqual(niveau(30, 30, 7), ATTENTION)
        self.assertEqual(niveau(31, 30, 7), OK)

    def test_valeurs_initiales_migrees(self):
        # La migration crée un couple de seuils par échéance
        self.assertEqual(seuils('ct'), (30, 7))
        self.assertEqual(seuils('revision'), (2000, 500))
        self.assertEqual(seuils('permis'), (60, 15))
        self.assertFalse(Parametre.objects.filter(cle='alerte_ct_jours').exists())


class EcheancesTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.flotte_global = cls.creer_utilisateur('flotte_global', 'responsable_flotte', None)
        cls.vehicule = Vehicule.objects.create(immatriculation='AA-100', agence=cls.agence_a, annee=2020,
                                               kilometrage_actuel=48000, kilometrage_revision=50000)
        cls.type_ct = TypeDocumentVehicule.objects.get(code='ct')

    def doc_ct(self, dans_jours):
        return DocumentVehicule.objects.create(
            vehicule=self.vehicule, type_document=self.type_ct, fichier='x.pdf',
            date_expiration=timezone.now().date() + datetime.timedelta(days=dans_jours),
        )

    # ── Enregistrement des seuils ─────────────────────────────────────
    def test_attention_doit_depasser_urgent(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post('/api/v1/parametrage/bulk_update/',
                                [{'cle': 'echeance_ct_attention', 'valeur': 5}], format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Contrôle technique', resp.data['detail'])
        self.assertEqual(seuils('ct'), (30, 7))

    def test_enregistrement_ok(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post('/api/v1/parametrage/bulk_update/', [
            {'cle': 'echeance_ct_attention', 'valeur': 45},
            {'cle': 'echeance_ct_urgent', 'valeur': 10},
            {'cle': 'conso_anomalie_pct', 'valeur': 25},
        ], format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(seuils('ct'), (45, 10))

    def test_cle_inconnue_refusee(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post('/api/v1/parametrage/bulk_update/',
                                [{'cle': 'nimporte_quoi', 'valeur': 1}], format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Le même seuil pilote l'État du parc et les alertes ────────────
    def test_seuil_ct_pilote_etat_parc_et_alertes(self):
        self.doc_ct(40)
        regler('ct', 30, 7)
        run_all_checks_sync()
        self.assertFalse(Alerte.objects.filter(type_alerte=Alerte.TypeAlerte.CT_EXPIRATION).exists())

        regler('ct', 45, 7)   # 40 jours restants → attention
        run_all_checks_sync()
        alerte = Alerte.objects.get(type_alerte=Alerte.TypeAlerte.CT_EXPIRATION)
        self.assertEqual(alerte.priorite, 'normale')

        self.client.force_authenticate(self.flotte_global)
        resp = self.client.get(reverse('vehicule-etat-parc'))
        ligne = next(v for v in resp.data['vehicules'] if v['immatriculation'] == 'AA-100')
        self.assertEqual(ligne['statut_ct'], 'attention')
        self.assertEqual(resp.data['seuils']['ct'], {'attention': 45, 'urgent': 7})

    def test_priorites_selon_niveau(self):
        doc = self.doc_ct(5)                       # urgent
        run_all_checks_sync()
        self.assertEqual(Alerte.objects.get(type_alerte=Alerte.TypeAlerte.CT_EXPIRATION).priorite, 'haute')
        doc.date_expiration = timezone.now().date() - datetime.timedelta(days=1)
        doc.save()
        run_all_checks_sync()
        self.assertEqual(Alerte.objects.get(type_alerte=Alerte.TypeAlerte.CT_EXPIREE).priorite, 'critique')

    def test_ancien_document_remplace_ignore(self):
        self.doc_ct(-100)   # ancien CT expiré
        self.doc_ct(200)    # nouveau CT valide
        run_all_checks_sync()
        self.assertFalse(Alerte.objects.filter(type_alerte=Alerte.TypeAlerte.CT_EXPIREE).exists())

    def test_revision_alerte_des_seuil_urgent(self):
        regler('revision', 3000, 2500)   # 2 000 km restants → urgent
        run_all_checks_sync()
        alerte = Alerte.objects.get(type_alerte=Alerte.TypeAlerte.REVISION_DUE)
        self.assertEqual(alerte.priorite, 'haute')
        self.assertIn('2000 km', alerte.message)


class ReferentielsTests(UtilisateursMixin, APITestCase):
    """Compteur d'utilisations et suppression protégée."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from .models import MarqueVehicule, ModeleVehicule, StatutVehicule
        cls.flotte_global = cls.creer_utilisateur('flotte_global2', 'responsable_flotte', None)
        cls.statut = StatutVehicule.objects.get(code='en_panne')
        cls.statut_libre = StatutVehicule.objects.create(code='test_libre', libelle='Libre')
        cls.marque = MarqueVehicule.objects.create(libelle='Toyota')
        cls.modele = ModeleVehicule.objects.create(marque=cls.marque, libelle='Hilux')
        Vehicule.objects.create(immatriculation='ZZ-1', agence=cls.agence_a, annee=2020,
                                statut=cls.statut, marque=cls.marque, modele=cls.modele)

    def setUp(self):
        self.client.force_authenticate(self.flotte_global)

    def test_compteurs(self):
        statuts = {s['code']: s['nb_utilisations']
                   for s in self.client.get(reverse('statut-vehicule-list')).data}
        self.assertEqual(statuts['en_panne'], 1)
        self.assertEqual(statuts['test_libre'], 0)
        modeles = self.client.get(reverse('modele-vehicule-list')).data
        self.assertEqual(next(m for m in modeles if m['libelle'] == 'Hilux')['nb_utilisations'], 1)

    def test_suppression_statut_utilise_refusee(self):
        resp = self.client.delete(reverse('statut-vehicule-detail', args=[self.statut.id]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('1 véhicule(s)', resp.data['detail'])
        self.assertTrue(Vehicule.objects.filter(statut=self.statut).exists())

    def test_suppression_modele_utilise_message_clair(self):
        resp = self.client.delete(reverse('modele-vehicule-detail', args=[self.modele.id]))
        self.assertEqual(resp.status_code, 400)
        resp = self.client.delete(reverse('marque-vehicule-detail', args=[self.marque.id]))
        self.assertEqual(resp.status_code, 400)

    def test_suppression_element_libre_ok(self):
        resp = self.client.delete(reverse('statut-vehicule-detail', args=[self.statut_libre.id]))
        self.assertEqual(resp.status_code, 204)

    def test_desactivation_puis_reactivation(self):
        from apps.entretien.models import TypeIntervention
        t = TypeIntervention.objects.create(nom='Vidange', categorie='preventif')
        url = reverse('type-intervention-detail', args=[t.id])
        self.assertEqual(self.client.patch(url, {'is_active': False}, format='json').status_code, 200)
        self.assertNotIn('Vidange', self.noms())             # formulaires : actifs seulement
        self.assertIn('Vidange', self.noms({'tous': 1}))     # page Paramètres : tous
        self.assertEqual(self.client.patch(url, {'is_active': True}, format='json').status_code, 200)

    def noms(self, params=None):
        data = self.client.get(reverse('type-intervention-list'), params or {}).data
        return [x['nom'] for x in (data['results'] if isinstance(data, dict) else data)]

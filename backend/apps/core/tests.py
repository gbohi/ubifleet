"""UbiFleet — Tests des permissions par rôle sur les modules."""

from django.urls import reverse
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from rest_framework.request import Request

from apps.accounts.permission_cache import invalidate
from apps.rapports.views import agence_autorisee
from .testing import UtilisateursMixin


class PermissionsModulesTests(UtilisateursMixin, APITestCase):

    def setUp(self):
        invalidate()

    def statut(self, user, method, url, data=None):
        self.client.force_authenticate(user)
        return getattr(self.client, method)(url, data or {}, format='json').status_code

    # ── Alertes ───────────────────────────────────────────────────────
    def test_alertes_consultables_par_tous(self):
        self.assertEqual(self.statut(self.chauffeur, 'get', reverse('alerte-list')), 200)

    def test_alertes_creation_et_generation_reservees(self):
        for user in (self.chauffeur, self.gestionnaire):
            self.assertEqual(self.statut(user, 'post', reverse('alerte-list'), {'titre': 'x'}), 403)
            self.assertEqual(self.statut(user, 'post', reverse('alerte-generer')), 403)

    # ── Chauffeurs (le ViewSet protégé de views.py est bien celui routé) ──
    def test_chauffeurs(self):
        self.assertEqual(self.statut(self.chauffeur, 'get', reverse('chauffeur-list')), 403)
        self.assertEqual(self.statut(self.operateur, 'get', reverse('chauffeur-list')), 200)
        self.assertEqual(self.statut(self.operateur, 'post', reverse('chauffeur-list'), {'nom': 'x'}), 403)

    # ── Contrôle véhicule ─────────────────────────────────────────────
    def test_controle_referentiel(self):
        url = reverse('element-controle-list')
        self.assertEqual(self.statut(self.chauffeur, 'get', url), 403)
        self.assertEqual(self.statut(self.operateur, 'get', url), 200)
        data = {'nom': 'Essuie-glaces', 'categorie': 'securite'}
        self.assertEqual(self.statut(self.gestionnaire, 'post', url, data), 403)
        self.assertEqual(self.statut(self.responsable_flotte, 'post', url, data), 201)

    # ── Référentiels du paramétrage ───────────────────────────────────
    def test_referentiels_parametrage(self):
        url = reverse('marque-vehicule-list')
        self.assertEqual(self.statut(self.chauffeur, 'get', url), 200)
        self.assertEqual(self.statut(self.gestionnaire, 'post', url, {'libelle': 'Toyota'}), 403)
        self.assertEqual(self.statut(self.responsable_flotte, 'post', url, {'libelle': 'Toyota'}), 201)

    # ── Entretien / sinistres / carburant ─────────────────────────────
    def test_referentiels_metier(self):
        for nom in ('prestataire-list', 'assureur-list', 'station-list'):
            url = reverse(nom)
            self.assertEqual(self.statut(self.chauffeur, 'get', url), 403, nom)
            self.assertEqual(self.statut(self.operateur, 'get', url), 200, nom)
            self.assertEqual(self.statut(self.operateur, 'post', url, {'nom': 'x'}), 403, nom)

    # ── Rapports ──────────────────────────────────────────────────────
    def test_rapports(self):
        self.assertEqual(self.statut(self.chauffeur, 'get', reverse('dashboard-dg')), 200)
        self.assertEqual(self.statut(self.chauffeur, 'get', reverse('rapport-couts')), 403)
        self.assertEqual(self.statut(self.gestionnaire, 'get', reverse('rapport-multi-agences')), 403)
        self.assertEqual(self.statut(self.responsable_flotte, 'get', reverse('rapport-multi-agences')), 200)

    def test_rapports_cloisonnes_par_agence(self):
        factory = APIRequestFactory()

        def agence_pour(user):
            django_request = factory.get('/', {'agence': str(self.agence_b.id)})
            force_authenticate(django_request, user=user)
            request = Request(django_request)
            request.user = user
            return agence_autorisee(request)

        # Rattaché à l'agence A (quel que soit le rôle) : toujours l'agence A
        self.assertEqual(agence_pour(self.gestionnaire), str(self.agence_a.id))
        self.assertEqual(agence_pour(self.responsable_flotte), str(self.agence_a.id))
        # « Toutes les agences » : le filtre demandé est respecté
        global_ = self.creer_utilisateur('global', 'gestionnaire', None)
        self.assertEqual(agence_pour(global_), str(self.agence_b.id))


class CloisonnementAgenceTests(UtilisateursMixin, APITestCase):
    """Règle : rattaché à une agence → ses données uniquement, quel que soit
    le rôle ; « Toutes les agences » (agence vide) → tout."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.vehicules.models import ReleveKilometrage, Vehicule
        cls.flotte_global = cls.creer_utilisateur('flotte_global', 'responsable_flotte', None)
        cls.veh_a = Vehicule.objects.create(immatriculation='AA-001', agence=cls.agence_a, annee=2020)
        cls.veh_b = Vehicule.objects.create(immatriculation='BB-001', agence=cls.agence_b, annee=2020)
        ReleveKilometrage.objects.create(vehicule=cls.veh_a, kilometrage=100, date_releve='2026-01-01')
        ReleveKilometrage.objects.create(vehicule=cls.veh_b, kilometrage=200, date_releve='2026-01-01')

    def setUp(self):
        invalidate()

    def lister(self, user, url, cle):
        self.client.force_authenticate(user)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        return sorted(str(x[cle]) for x in data)

    # ── Lecture ───────────────────────────────────────────────────────
    def test_vehicules_niveau_eleve_rattache_ne_voit_que_son_agence(self):
        url = reverse('vehicule-list')
        self.assertEqual(self.lister(self.responsable_flotte, url, 'immatriculation'), ['AA-001'])
        self.assertEqual(self.lister(self.super_admin, url, 'immatriculation'), ['AA-001'])
        self.assertEqual(self.lister(self.flotte_global, url, 'immatriculation'), ['AA-001', 'BB-001'])

    def test_vehicule_autre_agence_introuvable(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.get(reverse('vehicule-detail', args=[self.veh_b.id]))
        self.assertEqual(resp.status_code, 404)

    def test_releves_km_cloisonnes(self):
        url = '/api/v1/vehicules/releves-km/'
        self.assertEqual(self.lister(self.operateur, url, 'kilometrage'), ['100'])
        self.assertEqual(self.lister(self.flotte_global, url, 'kilometrage'), ['100', '200'])

    # ── Écriture ──────────────────────────────────────────────────────
    def test_creation_sur_vehicule_d_une_autre_agence_refusee(self):
        self.client.force_authenticate(self.operateur)
        url = '/api/v1/vehicules/releves-km/'
        data = {'kilometrage': 300, 'date_releve': '2026-02-01', 'type_mouvement': 'releve'}
        resp = self.client.post(url, {**data, 'vehicule': str(self.veh_b.id)}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        resp = self.client.post(url, {**data, 'vehicule': str(self.veh_a.id)}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_agence_imposee_a_la_creation(self):
        self.client.force_authenticate(self.responsable_flotte)
        url = reverse('marque-vehicule-list')  # référentiel sans agence : pas d'impact
        self.assertEqual(self.client.post(url, {'libelle': 'Isuzu'}, format='json').status_code, 201)
        from apps.vehicules.models import Vehicule
        resp = self.client.post(reverse('vehicule-list'), {
            'immatriculation': 'AA-002', 'annee': 2021, 'agence': str(self.agence_b.id),
        }, format='json')
        self.assertIn(resp.status_code, (400, 403), resp.data)
        self.assertFalse(Vehicule.objects.filter(immatriculation='AA-002', agence=self.agence_b).exists())

    # ── Utilisateurs et agences ───────────────────────────────────────
    def test_utilisateurs_cloisonnes(self):
        emails = self.lister(self.responsable_flotte, reverse('user-list'), 'email')
        self.assertNotIn('operateur_b@test.ci', emails)
        self.assertNotIn('flotte_global@test.ci', emails)
        self.assertIn('chauffeur@test.ci', emails)

    def test_utilisateur_cree_dans_son_agence_et_pas_en_toutes_agences(self):
        from apps.accounts.models import User
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post(reverse('user-list'), {
            'email': 'nouveau@test.ci', 'username': 'nouveau', 'first_name': 'N', 'last_name': 'N',
            'password': 'Motdepasse!2026', 'password2': 'Motdepasse!2026',
            'role': str(self.roles['chauffeur'].id),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(User.objects.get(email='nouveau@test.ci').agence, self.agence_a)

        resp = self.client.patch(reverse('user-detail', args=[self.chauffeur.id]),
                                 {'agence': None}, format='json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.patch(reverse('user-detail', args=[self.chauffeur.id]),
                                 {'agence': str(self.agence_b.id)}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.chauffeur.refresh_from_db()
        self.assertEqual(self.chauffeur.agence, self.agence_a)

    def test_agences_modifiables_seulement_la_sienne(self):
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.get(reverse('agence-list')).status_code, 200)
        self.assertEqual(self.lister(self.gestionnaire, reverse('agence-list'), 'code'), ['ABJ'])
        resp = self.client.patch(reverse('agence-detail', args=[self.agence_b.id]), {'ville': 'X'}, format='json')
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(reverse('agence-list'), {'nom': 'N', 'code': 'NEW', 'ville': 'N'}, format='json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.patch(reverse('agence-detail', args=[self.agence_a.id]), {'telephone': '0102'}, format='json')
        self.assertEqual(resp.status_code, 200)

    # ── Transactions Total et grand livre ─────────────────────────────
    def test_transactions_total_par_numero_client(self):
        from apps.total_import.models import ImportTotal, TransactionCarburant
        self.agence_a.numero_client_total = 'C-A'
        self.agence_a.save()
        imp = ImportTotal.objects.create(fichier_nom='t.csv')
        TransactionCarburant.objects.create(import_source=imp, numero_client='C-A', numero_ticket='1')
        TransactionCarburant.objects.create(import_source=imp, numero_client='C-B', numero_ticket='2')
        url = reverse('transaction-carburant-list')
        self.assertEqual(self.lister(self.gestionnaire, url, 'numero_ticket'), ['1'])
        self.assertEqual(self.lister(self.flotte_global, url, 'numero_ticket'), ['1', '2'])

    def test_grand_livre_par_code_agence(self):
        from apps.grand_livre.models import ImportGrandLivre, LigneGrandLivre
        imp = ImportGrandLivre.objects.create(fichier_nom='gl.xlsx')
        for code in ('ABJ', 'BKE'):
            LigneGrandLivre.objects.create(import_source=imp, code_agence=code, libelle_agence=code,
                                           compte='6061', libelle_compte='Carburant', piece=code)
        url = reverse('gl-ligne-list')
        self.assertEqual(self.lister(self.gestionnaire, url, 'code_agence'), ['ABJ'])
        self.assertEqual(self.lister(self.flotte_global, url, 'code_agence'), ['ABJ', 'BKE'])

    def test_import_total_reserve_toutes_agences(self):
        self.client.force_authenticate(self.gestionnaire)
        resp = self.client.post('/api/v1/total-import/historique/upload/', {}, format='multipart')
        self.assertEqual(resp.status_code, 403)


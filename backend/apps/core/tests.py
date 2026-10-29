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

        # Un gestionnaire de l'agence A ne peut pas consulter l'agence B
        self.assertEqual(agence_pour(self.gestionnaire), str(self.agence_a.id))
        # À partir du responsable flotte, le filtre demandé est respecté
        self.assertEqual(agence_pour(self.responsable_flotte), str(self.agence_b.id))

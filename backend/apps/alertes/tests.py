"""UbiFleet — Tests Alertes"""

from django.test import TestCase
from .models import Alerte


class TestAlerte(TestCase):
    """Tests pour le modèle Alerte."""

    def test_creation_alerte(self):
        """Vérifie la création d'une alerte"""
        # Test nécessite agence et fixtures
        pass



from rest_framework.test import APITestCase
from apps.core.testing import UtilisateursMixin


class CentreAlertesTests(UtilisateursMixin, APITestCase):
    """Résumé « à traiter », filtres, tri par priorité, clôture."""

    def setUp(self):
        from .models import Alerte
        for prio, statut, titre in (('normale', 'active', 'N'), ('critique', 'lue', 'C'),
                                    ('haute', 'active', 'H'), ('haute', 'traitee', 'T')):
            Alerte.objects.create(type_alerte='revision_due', priorite=prio, statut=statut, titre=titre,
                                  message='m', agence=self.agence_a)
        Alerte.objects.create(type_alerte='vignette_exp', titre='Vignette AB-1', message='m', agence=self.agence_a)
        self.client.force_authenticate(self.responsable_flotte)

    def test_resume_et_liste(self):
        r = self.client.get('/api/v1/alertes/resume/').data
        self.assertEqual((r['total'], r['non_lues'], r['critiques'], r['hautes']), (4, 3, 1, 1))
        lst = self.client.get('/api/v1/alertes/', {'statut': 'a_traiter'}).data['results']
        # Priorité d'abord, puis la plus récente
        self.assertEqual([a['titre'] for a in lst], ['C', 'H', 'Vignette AB-1', 'N'])
        v = self.client.get('/api/v1/alertes/', {'search': 'vignette'}).data['results']
        self.assertEqual(v[0]['type_display'], 'Vignette expirant bientôt')
        types = {t['code'] for t in self.client.get('/api/v1/alertes/types/').data}
        self.assertIn('controle_non_conforme', types)

    def test_cloture_unique(self):
        from .models import Alerte
        a = Alerte.objects.get(titre='H')
        self.assertEqual(self.client.post(f'/api/v1/alertes/{a.id}/ignorer/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/v1/alertes/{a.id}/traiter/').status_code, 400)
        a.refresh_from_db()
        self.assertEqual(a.traitee_par, self.responsable_flotte)

"""UbiFleet — Tests Rapports"""

from django.test import TestCase
from rest_framework.test import APITestCase
from apps.core.testing import UtilisateursMixin


# Les tests seront ajoutés au fur et à mesure du développement


class RapportCoutsTests(UtilisateursMixin, APITestCase):
    """Coûts annuels : comparaison N-1, budget par poste, répartitions, véhicules."""

    def test_rapport_couts(self):
        import datetime
        from apps.budget.models import BudgetAnnuel, DepenseVehicule
        from apps.vehicules.models import Vehicule
        v = Vehicule.objects.create(immatriculation='RC-1', agence=self.agence_a, annee=2020)
        for annee, cat, montant, vh in ((2026, 'reparation', 300, v), (2026, 'sinistre', 100, v),
                                        (2026, 'peage', 100, None), (2025, 'reparation', 250, v)):
            DepenseVehicule.objects.create(agence=self.agence_a, vehicule=vh, categorie=cat, montant=montant,
                                           date_depense=datetime.date(annee, 3, 1), description='x')
        BudgetAnnuel.objects.create(agence=self.agence_a, annee=2026, budget_reparations=800)
        self.client.force_authenticate(self.responsable_flotte)
        d = self.client.get('/api/v1/rapports/couts/', {'annee': 2026}).data
        self.assertEqual((d['total'], d['total_precedent'], d['variation']), (500.0, 250.0, 100.0))
        self.assertEqual(d['taux_budget'], 62.5)
        rep = next(b for b in d['budget'] if b['poste'] == 'reparations')
        self.assertEqual((rep['prevu'], rep['realise'], rep['ecart'], rep['taux']), (800.0, 400.0, 400.0, 50.0))
        self.assertEqual(d['evolution'][2]['total'], 500.0)
        self.assertEqual(d['evolution'][2]['total_precedent'], 250.0)
        self.assertEqual(d['top_vehicules'][0]['postes'], {'reparations': 400.0})
        self.assertEqual(d['par_origine'][0]['libelle'], 'Saisie manuelle')

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


class RapportsLibellesTests(UtilisateursMixin, APITestCase):
    """Libellés lisibles (statuts, types paramétrables) et montants des sinistres."""

    def test_sinistres_effectif_dashboard(self):
        import datetime
        from decimal import Decimal
        from apps.sinistres.models import Sinistre
        from apps.vehicules.models import Vehicule
        v = Vehicule.objects.create(immatriculation='RL-1', agence=self.agence_a, annee=2020, type_vehicule='pickup')
        Sinistre.objects.create(vehicule=v, agence=self.agence_a, type_sinistre='accident', statut='indemnise',
                                date_sinistre='2026-05-01', description='x',
                                cout_reparation=Decimal('1000'), indemnisation_recue=Decimal('800'))
        self.client.force_authenticate(self.responsable_flotte)
        s = self.client.get('/api/v1/rapports/sinistres/').data
        self.assertEqual((s['cout_total'], s['indemnisation_total'], s['reste_a_charge']), (1000.0, 800.0, 200.0))
        self.assertEqual(s['par_statut'][0]['libelle'], 'Indemnisé')
        e = self.client.get('/api/v1/rapports/effectif-parc/').data
        self.assertEqual(e['par_type'][0]['label'], 'Pick-up')
        d = self.client.get('/api/v1/rapports/dashboard/', {'mois': 2, 'annee': 2026}).data
        mois = [(m['annee'], m['mois']) for m in d['cout_mensuel']]
        self.assertEqual((mois[0], mois[-1], len(set(mois))), ((2025, 3), (2026, 2), 12))   # 12 mois distincts finissant au mois choisi


class TableauDeBordTests(UtilisateursMixin, APITestCase):
    """Page d'accueil : statuts paramétrés, alertes prioritaires, échéances chauffeurs."""

    def test_accueil(self):
        import datetime
        from django.utils import timezone
        from apps.alertes.models import Alerte
        from apps.chauffeurs.models import Chauffeur
        from apps.parametrage.models import StatutVehicule
        from apps.vehicules.models import Vehicule
        st = StatutVehicule.objects.get(code='en_panne')
        v = Vehicule.objects.create(immatriculation='TB-1', agence=self.agence_a, annee=2020, statut=st)
        Vehicule.objects.create(immatriculation='TB-2', agence=self.agence_a, annee=2020)        # sans statut
        Chauffeur.objects.create(matricule='TB-C', nom='N', prenom='P', numero_permis='X', categories_permis='B',
                                 agence=self.agence_a, date_expiration_permis=timezone.localdate() - datetime.timedelta(days=1))
        for prio, titre in (('normale', 'N'), ('critique', 'C'), ('haute', 'H')):
            Alerte.objects.create(type_alerte='revision_due', priorite=prio, titre=titre, message='m',
                                  vehicule=v, agence=self.agence_a)
        Alerte.objects.create(type_alerte='revision_due', priorite='critique', titre='Traitée', message='m',
                              vehicule=v, agence=self.agence_a, statut='traitee')
        self.client.force_authenticate(self.responsable_flotte)
        d = self.client.get('/api/v1/rapports/dashboard/').data
        statuts = {s['libelle']: s['nb'] for s in d['parc']['par_statut']}
        self.assertEqual(statuts, {'En panne': 1, 'Sans statut': 1})
        self.assertEqual([a['titre'] for a in d['alertes']['prioritaires']], ['C', 'H', 'N'])   # traitée exclue
        self.assertEqual((d['alertes']['total'], d['alertes']['critiques']), (3, 1))
        self.assertEqual(d['chauffeurs']['permis_expires'], 1)

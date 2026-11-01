"""UbiFleet — Tests Budget : dépenses reportées automatiquement et état des dépenses."""

import datetime
from decimal import Decimal

from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from apps.vehicules.models import Vehicule
from .models import DepenseVehicule

URL = '/api/v1/budget/depenses/'


class DepensesAutomatiquesTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.v = Vehicule.objects.create(immatriculation='BG-1', agence=cls.agence_a, annee=2020)

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def depense(self, ref):
        return DepenseVehicule.objects.filter(ref_objet_type=ref).first()

    def test_intervention_terminee(self):
        from apps.entretien.models import Intervention, TypeIntervention
        t = TypeIntervention.objects.create(nom='Embrayage', categorie='curatif')
        i = Intervention.objects.create(vehicule=self.v, type_intervention=t, agence=self.agence_a,
                                        date_planifiee='2026-04-01', cout_reel=Decimal('250000'))
        self.assertIsNone(self.depense('intervention'))            # pas encore terminée
        i.statut = 'termine'
        i.date_fin = datetime.date(2026, 4, 3)
        i.save()
        d = self.depense('intervention')
        self.assertEqual((d.categorie, d.montant, d.date_depense), ('reparation', Decimal('250000'), datetime.date(2026, 4, 3)))
        # Modifiable uniquement par l'intervention
        r = self.client.patch(f'{URL}{d.id}/', {'montant': '1'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('intervention', str(r.data))
        i.delete()
        self.assertIsNone(self.depense('intervention'))

    def test_contrat_pneu_et_sinistre(self):
        from apps.entretien.models import SuiviPneus
        from apps.sinistres.models import Assureur, ContratAssurance, Sinistre
        assureur = Assureur.objects.create(nom='NSIA')
        ContratAssurance.objects.create(vehicule=self.v, assureur=assureur, numero_police='P-1', type_contrat='rc',
                                        date_debut='2026-01-01', date_fin='2026-12-31', prime_annuelle=Decimal('300000'))
        d = self.depense('contrat_assurance')
        self.assertEqual((d.categorie, d.montant, d.agence_id, d.fournisseur), ('assurance', Decimal('300000'), self.agence_a.id, 'NSIA'))
        # Pneu : coût informatif, compté par l'intervention (pas de double compte)
        SuiviPneus.objects.create(vehicule=self.v, position='av_gauche', date_montage='2026-02-01', cout=Decimal('60000'))
        self.assertIsNone(self.depense('pneu'))
        # Sinistre : réparation − indemnisation reçue
        s = Sinistre.objects.create(vehicule=self.v, agence=self.agence_a, type_sinistre='accident',
                                    date_sinistre='2026-05-01', description='Choc')
        self.assertIsNone(self.depense('sinistre'))                # coût pas encore connu
        s.cout_reparation = Decimal('1000000')
        s.save()
        self.assertEqual(self.depense('sinistre').montant, Decimal('1000000'))   # avance tant que non indemnisé
        s.indemnisation_recue = Decimal('800000')
        s.save()
        self.assertEqual(self.depense('sinistre').montant, Decimal('200000'))
        s.indemnisation_recue = Decimal('1000000')
        s.save()
        self.assertIsNone(self.depense('sinistre'))                # entièrement remboursé

    def test_etat_et_filtres(self):
        from apps.parametrage.models import CategorieDepense
        for cat, montant, jour in (('reparation', 100, 1), ('sinistre', 300, 2), ('peage', 50, 3), ('reparation', 50, 20)):
            DepenseVehicule.objects.create(agence=self.agence_a, vehicule=self.v, categorie=cat, montant=montant,
                                           date_depense=datetime.date(2026, 6, jour), description=cat)
        # Filtres de la liste (catégorie, période, poste, origine)
        self.assertEqual(self.client.get(URL, {'categorie': 'reparation'}).data['count'], 2)
        self.assertEqual(self.client.get(URL, {'date_min': '2026-06-02', 'date_max': '2026-06-10'}).data['count'], 2)
        self.assertEqual(self.client.get(URL, {'poste': 'reparations'}).data['count'], 3)   # réparation + sinistre
        self.assertEqual(self.client.get(URL, {'origine': 'manuelle'}).data['count'], 4)
        self.assertEqual(self.client.get(URL, {'origine': 'intervention'}).data['count'], 0)
        e = self.client.get(f'{URL}etat/', {'date_max': '2026-06-10'}).data
        self.assertEqual((e['total'], e['nb']), (450.0, 3))
        self.assertEqual(e['par_categorie'][0]['libelle'], 'Sinistre')
        reparations = next(p for p in e['par_poste'] if p['poste'] == 'reparations')
        self.assertEqual((reparations['total'], reparations['part']), (400.0, 88.9))
        self.assertEqual(e['par_origine'][0]['libelle'], 'Saisie manuelle')
        # Catégories alimentées automatiquement : verrouillées
        self.assertTrue(CategorieDepense.objects.get(code='reparation').systeme)

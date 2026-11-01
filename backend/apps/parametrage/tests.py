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
from .models import Parametre, Tournee, TypeMouvement


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


class TypesMouvementTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.vehicule = Vehicule.objects.create(immatriculation='TM-1', agence=cls.agence_a, annee=2020)

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def releve(self, type_mouvement):
        return self.client.post('/api/v1/vehicules/releves-km/', {
            'vehicule': str(self.vehicule.id), 'kilometrage': 1000,
            'date_releve': '2026-03-01', 'type_mouvement': type_mouvement}, format='json')

    def test_types_initiaux_et_nouveau_type(self):
        types = self.client.get(reverse('type-mouvement-list')).data
        self.assertEqual([t['code'] for t in types if t['pour_releves']], ['releve', 'sortie', 'entree', 'tournee'])
        self.assertEqual([t['code'] for t in types if t['pour_prises']], ['tournee', 'course', 'ramassage', 'mission'])
        resp = self.client.post(reverse('type-mouvement-list'),
                                {'code': 'atelier', 'libelle': 'Entrée atelier', 'couleur': 'orange'}, format='json')
        self.assertEqual(resp.status_code, 201)
        resp = self.releve('atelier')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type_display'], 'Entrée atelier')

    def test_type_inconnu_ou_desactive_refuse(self):
        self.assertEqual(self.releve('inexistant').status_code, 400)
        from .models import TypeMouvement
        TypeMouvement.objects.filter(code='sortie').update(actif=False)
        self.assertEqual(self.releve('sortie').status_code, 400)

    def test_suppression_type_utilise_refusee_et_code_fige(self):
        self.releve('tournee')
        from .models import TypeMouvement
        t = TypeMouvement.objects.get(code='tournee')
        resp = self.client.delete(reverse('type-mouvement-detail', args=[t.id]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('relevé', resp.data['detail'])
        resp = self.client.patch(reverse('type-mouvement-detail', args=[t.id]), {'code': 'autre'}, format='json')
        self.assertEqual(resp.status_code, 400)


class DotationTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.demandes.models import NiveauValidation, TypeDemande
        from .models import Tournee
        cls.tournee = Tournee.objects.create(code='NORD1', libelle='Nord', agence=cls.agence_a, dotation=100)
        # Circuit dotation : une étape validée par le DG
        type_dotation = TypeDemande.objects.get(code='dotation')
        NiveauValidation.objects.filter(type_demande=type_dotation).update(role_min=cls.roles['dg'])

    def url(self, action):
        return reverse(f'tournee-{action}', args=[self.tournee.id])

    def demander(self, valeur=120, user=None):
        self.client.force_authenticate(user or self.responsable_flotte)
        return self.client.post(self.url('demander-dotation'),
                                {'nouvelle_dotation': valeur, 'motif': 'Extension de la tournée'}, format='json')

    def test_modification_directe_interdite(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.patch(reverse('tournee-detail', args=[self.tournee.id]), {'dotation': 500}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.patch(reverse('tournee-detail', args=[self.tournee.id]), {'libelle': 'Nord 1'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_circuit_complet(self):
        from apps.demandes.models import Demande
        resp = self.demander()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.tournee.refresh_from_db()
        self.assertEqual(self.tournee.dotation, 100)          # inchangée avant validation
        detail = self.client.get(reverse('tournee-detail', args=[self.tournee.id])).data
        self.assertEqual(detail['dotation_en_attente'], 120)

        demande = Demande.objects.get(changement_dotation__isnull=False)
        self.assertEqual(demande.statut, Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.responsable_flotte)   # le demandeur ne valide pas
        self.assertEqual(self.client.post(reverse('demande-valider', args=[demande.id])).status_code, 403)
        self.client.force_authenticate(self.dg)
        self.assertEqual(self.client.post(reverse('demande-valider', args=[demande.id])).status_code, 200)

        self.tournee.refresh_from_db()
        self.assertEqual(self.tournee.dotation, 120)
        self.client.force_authenticate(self.responsable_flotte)
        histo = self.client.get(self.url('historique-dotation')).data
        self.assertEqual([h['statut'] for h in histo], ['approuvee'])
        self.assertEqual((histo[0]['ancienne_dotation'], histo[0]['nouvelle_dotation']), (100, 120))

    def test_rejet_ne_change_rien(self):
        from apps.demandes.models import Demande
        self.demander()
        demande = Demande.objects.get(changement_dotation__isnull=False)
        self.client.force_authenticate(self.dg)
        self.client.post(reverse('demande-rejeter', args=[demande.id]), {'commentaire': 'Non justifié'}, format='json')
        self.tournee.refresh_from_db()
        self.assertEqual(self.tournee.dotation, 100)
        self.assertEqual(self.tournee.changements_dotation.get().statut, 'rejetee')

    def test_une_seule_demande_en_attente_et_motif_obligatoire(self):
        self.assertEqual(self.demander().status_code, 201)
        self.assertEqual(self.demander(150).status_code, 400)
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post(self.url('demander-dotation'), {'nouvelle_dotation': 90}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_demande_dotation_non_creable_depuis_demandes(self):
        from apps.demandes.models import TypeDemande
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.post(reverse('demande-list'), {
            'type_demande': TypeDemande.objects.get(code='dotation').id, 'titre': 'x', 'description': 'y'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creation_enregistre_la_dotation_initiale(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post(reverse('tournee-list'), {
            'code': 'SUD1', 'libelle': 'Sud', 'agence': str(self.agence_a.id), 'dotation': 80, 'km_theorique': 300},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        histo = self.client.get(reverse('tournee-historique-dotation', args=[resp.data['id']])).data
        self.assertEqual([(h['statut'], h['nouvelle_dotation']) for h in histo], [('initiale', 80)])


class FenetreSaisieTests(UtilisateursMixin, APITestCase):
    """Fenêtre de saisie des pleins et relevés : dates hors fenêtre refusées,
    données figées, exception par le droit « Saisie hors délai »."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.vehicules.models import Vehicule
        cls.vehicule = Vehicule.objects.create(immatriculation='FS-1', agence=cls.agence_a, annee=2020,
                                               type_carburant='diesel')
        cls.tournee = Tournee.objects.create(code='FS-T', libelle='Tournée FS', agence=cls.agence_a)
        cls.auj = timezone.localdate()

    def setUp(self):
        from apps.accounts.permission_cache import invalidate
        invalidate()   # règles de permission créées par un test précédent
        Parametre.objects.update_or_create(cle='fenetre_saisie_carburant_jours',
                                           defaults={'valeur': '3', 'type_valeur': 'int'})
        Parametre.objects.update_or_create(cle='fenetre_saisie_releves_jours',
                                           defaults={'valeur': '3', 'type_valeur': 'int'})

    def jour(self, n):
        return (self.auj - datetime.timedelta(days=n)).isoformat()

    def plein(self, user, n, km=1000):
        self.client.force_authenticate(user)
        return self.client.post('/api/v1/carburant/pleins/', {
            'vehicule': str(self.vehicule.id), 'date_plein': self.jour(n), 'heure_plein': '08:00',
            'type_mouvement': 'tournee', 'tournee': self.tournee.id, 'volume_litres': 30,
            'montant_fcfa': 21000, 'kilometrage_releve': km, 'agence': str(self.agence_a.id),
        }, format='json')

    def test_fenetre_exposee(self):
        self.client.force_authenticate(self.operateur)
        resp = self.client.get('/api/v1/parametrage/fenetre-saisie/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['carburant']['date_min'], self.auj - datetime.timedelta(days=2))
        self.assertEqual(resp.data['carburant']['date_max'], self.auj)
        self.assertFalse(resp.data['carburant']['hors_delai'])
        self.client.force_authenticate(self.responsable_flotte)
        self.assertTrue(self.client.get('/api/v1/parametrage/fenetre-saisie/').data['releves']['hors_delai'])

    def test_plein_dans_et_hors_fenetre(self):
        self.assertEqual(self.plein(self.operateur, 2).status_code, 201)
        resp = self.plein(self.operateur, 3)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('date_plein', resp.data)
        self.assertEqual(self.plein(self.operateur, -1).status_code, 400)   # futur

    def test_futur_refuse_meme_desactivee(self):
        Parametre.objects.filter(cle='fenetre_saisie_carburant_jours').update(valeur='0')
        self.assertEqual(self.plein(self.operateur, 400).status_code, 201)
        self.assertEqual(self.plein(self.responsable_flotte, -1).status_code, 400)

    def test_hors_delai_trace(self):
        resp = self.plein(self.responsable_flotte, 10)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['saisie_hors_delai'])
        self.assertEqual(resp.data['hors_delai_par'], self.responsable_flotte.id)
        self.assertFalse(self.plein(self.responsable_flotte, 0, km=1100).data['saisie_hors_delai'])

    def test_plein_fige(self):
        from apps.carburant.models import PleinsCarburant
        p = PleinsCarburant.objects.create(vehicule=self.vehicule, agence=self.agence_a, volume_litres=30,
                                           montant_fcfa=21000, kilometrage_releve=900,
                                           date_plein=self.auj - datetime.timedelta(days=5))
        url = f'/api/v1/carburant/pleins/{p.id}/'
        self.client.force_authenticate(self.gestionnaire)
        self.assertTrue(self.client.get(url).data['verrouille'])
        self.assertEqual(self.client.patch(url, {'notes': 'x'}, format='json').status_code, 403)
        # Ramener la date dans la fenêtre ne débloque pas non plus
        self.assertEqual(self.client.patch(url, {'date_plein': self.jour(0)}, format='json').status_code, 403)
        self.client.force_authenticate(self.responsable_flotte)
        self.assertFalse(self.client.get(url).data['verrouille'])
        self.assertEqual(self.client.patch(url, {'notes': 'corrigé'}, format='json').status_code, 400)  # motif
        resp = self.client.patch(url, {'notes': 'corrigé', 'motif_correction': 'Bon retrouvé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['saisie_hors_delai'])

    def test_plein_recent_modifiable_mais_pas_deplace_hors_fenetre(self):
        resp = self.plein(self.gestionnaire, 1)
        url = f"/api/v1/carburant/pleins/{resp.data['id']}/"
        self.assertEqual(self.client.patch(url, {'notes': 'ok'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'date_plein': self.jour(6)}, format='json').status_code, 400)

    def test_droit_hors_delai_parametrable(self):
        from apps.accounts.models import PermissionRole
        from apps.accounts.permission_cache import invalidate as invalidate_cache
        PermissionRole.objects.create(role=self.roles['operateur'], module='carburant',
                                      action='saisie_hors_delai', autorise=True)
        invalidate_cache()
        self.assertEqual(self.plein(self.operateur, 10).status_code, 201)
        self.client.force_authenticate(self.operateur)
        acces = self.client.get('/api/v1/auth/me/acces/').data
        self.assertTrue(acces['carburant_hors_delai'])
        self.assertFalse(acces['releves_hors_delai'])

    def test_releves(self):
        from apps.vehicules.models import ReleveKilometrage
        self.client.force_authenticate(self.operateur)
        url = f'/api/v1/vehicules/{self.vehicule.id}/kilometrage/'
        self.assertEqual(self.client.post(url, {'kilometrage': 500, 'date_releve': self.jour(5)}).status_code, 400)
        self.vehicule.refresh_from_db()
        self.assertEqual(self.vehicule.kilometrage_actuel, 0)   # rien enregistré
        self.assertEqual(self.client.post(url, {'kilometrage': 500, 'date_releve': self.jour(0)}).status_code, 200)
        resp = self.client.post('/api/v1/vehicules/releves-km/', {
            'vehicule': str(self.vehicule.id), 'kilometrage': 600, 'date_releve': self.jour(4)}, format='json')
        self.assertEqual(resp.status_code, 400)
        vieux = ReleveKilometrage.objects.create(vehicule=self.vehicule, kilometrage=100,
                                                 date_releve=self.auj - datetime.timedelta(days=8))
        self.client.force_authenticate(self.responsable_flotte)
        self.assertEqual(self.client.delete(f'/api/v1/vehicules/releves-km/{vieux.id}/').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/v1/vehicules/releves-km/{vieux.id}/?motif=Doublon').status_code, 204)
        vieux = ReleveKilometrage.objects.create(vehicule=self.vehicule, kilometrage=100,
                                                 date_releve=self.auj - datetime.timedelta(days=8))
        # Le droit hors délai du responsable flotte retiré : relevé figé
        from apps.accounts.models import PermissionRole
        from apps.accounts.permission_cache import invalidate as invalidate_cache
        PermissionRole.objects.create(role=self.roles['responsable_flotte'], module='releves_km',
                                      action='saisie_hors_delai', autorise=False)
        invalidate_cache()
        self.assertEqual(self.client.delete(f'/api/v1/vehicules/releves-km/{vieux.id}/').status_code, 403)

    def test_parametre_desactivable(self):
        self.client.force_authenticate(self.responsable_flotte)
        resp = self.client.post('/api/v1/parametrage/bulk_update/',
                                [{'cle': 'fenetre_saisie_releves_jours', 'valeur': 0}], format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.client.post('/api/v1/parametrage/bulk_update/',
                                          [{'cle': 'fenetre_saisie_releves_jours', 'valeur': -1}],
                                          format='json').status_code, 400)



class CorrectionSaisieTests(UtilisateursMixin, APITestCase):
    """Corrections de pleins et relevés : droits de l'auteur, kilométrage
    contrôlé par rapport aux saisies voisines, recalcul du compteur, journal."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.vehicules.models import Vehicule
        cls.vehicule = Vehicule.objects.create(immatriculation='CS-1', agence=cls.agence_a, annee=2020,
                                               type_carburant='diesel', kilometrage_actuel=10000,
                                               kilometrage_initial=10000)
        cls.tournee = Tournee.objects.create(code='CS-T', libelle='Tournée CS', agence=cls.agence_a)
        cls.auj = timezone.localdate()

    def setUp(self):
        from apps.accounts.permission_cache import invalidate
        invalidate()
        Parametre.objects.update_or_create(cle='fenetre_saisie_carburant_jours',
                                           defaults={'valeur': '3', 'type_valeur': 'int'})
        Parametre.objects.update_or_create(cle='fenetre_saisie_releves_jours',
                                           defaults={'valeur': '3', 'type_valeur': 'int'})

    def jour(self, n):
        return (self.auj - datetime.timedelta(days=n)).isoformat()

    def plein(self, user, n, km, litres=40, heure='08:00'):
        self.client.force_authenticate(user)
        return self.client.post('/api/v1/carburant/pleins/', {
            'vehicule': str(self.vehicule.id), 'date_plein': self.jour(n), 'heure_plein': heure,
            'type_mouvement': 'tournee', 'tournee': self.tournee.id, 'volume_litres': litres, 'montant_fcfa': 28000, 'kilometrage_releve': km,
            'agence': str(self.agence_a.id),
        }, format='json')

    def releve(self, user, n, km, heure=None):
        self.client.force_authenticate(user)
        data = {'vehicule': str(self.vehicule.id), 'kilometrage': km, 'date_releve': self.jour(n)}
        if heure:
            data['heure_releve'] = heure
        return self.client.post('/api/v1/vehicules/releves-km/', data, format='json')

    def test_tournee_du_releve(self):
        self.client.force_authenticate(self.operateur)
        url = '/api/v1/vehicules/releves-km/'
        base = {'vehicule': str(self.vehicule.id), 'date_releve': self.jour(0), 'heure_releve': '08:00'}
        resp = self.client.post(url, {**base, 'kilometrage': 10100, 'type_mouvement': 'tournee'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tournee', resp.data)
        resp = self.client.post(url, {**base, 'kilometrage': 10100, 'type_mouvement': 'tournee',
                                      'tournee': self.tournee.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['tournee_code'], 'CS-T')
        # Autre type : la tournée est ignorée
        resp = self.client.post(url, {**base, 'heure_releve': '09:00', 'kilometrage': 10150,
                                      'type_mouvement': 'releve', 'tournee': self.tournee.id}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data['tournee'])
        # Même règle depuis la fiche véhicule
        resp = self.client.post(f'/api/v1/vehicules/{self.vehicule.id}/kilometrage/',
                                {'kilometrage': 10200, 'date_releve': self.jour(0), 'heure_releve': '10:00',
                                 'type_mouvement': 'tournee'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tournee', resp.data)

    def test_type_tournee_reserve(self):
        self.client.force_authenticate(self.super_admin)
        t = TypeMouvement.objects.get(code='tournee')
        resp = self.client.delete(f'/api/v1/parametrage/types-mouvement/{t.id}/')
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(TypeMouvement.objects.filter(code='tournee').exists())

    def test_plein_valide_des_l_enregistrement_et_agence_du_vehicule(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.post('/api/v1/carburant/pleins/', {
            'vehicule': str(self.vehicule.id), 'date_plein': self.jour(0), 'heure_plein': '08:00',
            'type_mouvement': 'tournee', 'tournee': self.tournee.id, 'volume_litres': 30, 'montant_fcfa': 21000,
            'kilometrage_releve': 10100}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut_validation'], 'valide')
        self.assertEqual(str(resp.data['agence']), str(self.agence_a.id))

    def test_heure_du_plein_obligatoire(self):
        resp = self.plein(self.operateur, 1, 10100, heure=None)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('heure_plein', resp.data)
        # Plein ancien sans heure : modifiable sans la renseigner, mais on ne peut pas l'effacer
        from apps.carburant.models import PleinsCarburant
        ancien = PleinsCarburant.objects.create(vehicule=self.vehicule, agence=self.agence_a, volume_litres=30, montant_fcfa=21000,
                                                kilometrage_releve=10200, date_plein=self.auj, created_by=self.dg)
        self.client.force_authenticate(self.dg)
        url = f'/api/v1/carburant/pleins/{ancien.id}/'
        self.assertEqual(self.client.patch(url, {'notes': 'ok', 'motif_correction': 'x'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'heure_plein': None}, format='json').status_code, 400)

    def test_saisies_du_meme_jour_comparees_par_heure(self):
        self.assertEqual(self.releve(self.operateur, 0, 11000, heure='08:00').status_code, 201)
        # Plein à 10 h inférieur au relevé de 8 h : refusé, le message cite l'heure
        resp = self.plein(self.operateur, 0, 10900, heure='10:00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('à 08:00', str(resp.data['kilometrage_releve']))
        # Relevé à 7 h supérieur à celui de 8 h : refusé
        self.assertEqual(self.releve(self.operateur, 0, 11200, heure='07:00').status_code, 400)
        # Dans l'ordre des heures : accepté
        self.assertEqual(self.plein(self.operateur, 0, 10950, heure='06:30').status_code, 201)
        self.assertEqual(self.releve(self.operateur, 0, 11100, heure='12:00').status_code, 201)
        # Saisie du même jour sans heure (antérieure à l'heure obligatoire) : non comparée
        from apps.vehicules.models import ReleveKilometrage
        ReleveKilometrage.objects.create(vehicule=self.vehicule, kilometrage=99999, date_releve=self.auj)
        self.assertEqual(self.releve(self.operateur, 0, 11150, heure='13:00').status_code, 201)

    def test_heure_du_releve_par_defaut(self):
        resp = self.releve(self.operateur, 0, 10100)
        self.assertEqual(resp.status_code, 201)
        self.assertIsNotNone(resp.data['heure_releve'])     # aujourd'hui : heure du serveur
        resp = self.releve(self.operateur, 1, 10050)
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data['heure_releve'])        # date passée : pas d'heure inventée
        self.client.force_authenticate(self.operateur)
        self.assertIn('maintenant', self.client.get('/api/v1/parametrage/fenetre-saisie/').data)

    def km(self):
        self.vehicule.refresh_from_db()
        return self.vehicule.kilometrage_actuel

    def test_erreur_de_kilometrage_corrigee_par_l_auteur(self):
        resp = self.plein(self.operateur, 1, 125000)          # 125 000 au lieu de 12 500
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.km(), 125000)
        self.assertTrue(resp.data['modifiable'])
        self.assertTrue(resp.data['supprimable'])
        url = f"/api/v1/carburant/pleins/{resp.data['id']}/"
        resp = self.client.patch(url, {'kilometrage_releve': 12500}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.km(), 12500)
        from .models import CorrectionSaisie
        c = CorrectionSaisie.objects.get(objet_id=resp.data['id'])
        self.assertEqual(c.auteur, self.operateur)
        self.assertEqual([(x['champ'], x['avant'], x['apres']) for x in c.changements],
                         [('kilometrage_releve', '125000', '12500')])

    def test_suppression_recalcule_le_compteur(self):
        resp = self.releve(self.operateur, 0, 99999)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.km(), 99999)
        self.assertEqual(self.client.delete(f"/api/v1/vehicules/releves-km/{resp.data['id']}/").status_code, 204)
        self.assertEqual(self.km(), 10000)                      # kilométrage d'entrée dans le parc

    def test_droits_de_l_auteur_limites(self):
        resp = self.plein(self.operateur, 0, 11000)
        url = f"/api/v1/carburant/pleins/{resp.data['id']}/"
        self.client.force_authenticate(self.operateur_b)        # autre agence : invisible
        self.assertEqual(self.client.patch(url, {'notes': 'x'}, format='json').status_code, 404)
        autre = self.creer_utilisateur('operateur_a2', 'operateur', self.agence_a)
        self.client.force_authenticate(autre)
        self.assertFalse(self.client.get(url).data['modifiable'])
        self.assertEqual(self.client.patch(url, {'notes': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        # Sa propre saisie sortie de la fenêtre : figée
        from apps.carburant.models import PleinsCarburant
        vieux = PleinsCarburant.objects.create(vehicule=self.vehicule, agence=self.agence_a, volume_litres=30,
                                               montant_fcfa=1, kilometrage_releve=10500, created_by=self.operateur,
                                               date_plein=self.auj - datetime.timedelta(days=6))
        self.client.force_authenticate(self.operateur)
        self.assertEqual(self.client.delete(f'/api/v1/carburant/pleins/{vieux.id}/').status_code, 403)

    def test_kilometrage_controle_par_les_saisies_voisines(self):
        self.assertEqual(self.releve(self.gestionnaire, 1, 12000).status_code, 201)
        resp = self.releve(self.gestionnaire, 0, 11000)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('relevé du', resp.data['kilometrage'][0])
        # Relevé antérieur plus faible accepté, sans faire baisser le compteur
        self.assertEqual(self.releve(self.gestionnaire, 2, 11500).status_code, 201)
        self.assertEqual(self.km(), 12000)
        self.assertEqual(self.releve(self.gestionnaire, 2, 12500).status_code, 400)   # > relevé suivant

    def test_consommation_du_plein_suivant_recalculee(self):
        p1 = self.plein(self.gestionnaire, 2, 10400).data
        p2 = self.plein(self.gestionnaire, 1, 10800, litres=40).data
        self.assertEqual(float(p2['consommation_calculee']), 10.0)
        self.client.patch(f"/api/v1/carburant/pleins/{p1['id']}/", {'kilometrage_releve': 10000}, format='json')
        from apps.carburant.models import PleinsCarburant
        p2 = PleinsCarburant.objects.get(pk=p2['id'])
        self.assertEqual(p2.kilometrage_depart, 10000)
        self.assertEqual(float(p2.consommation_calculee), 5.0)

    def test_journal_consultable(self):
        resp = self.releve(self.operateur, 0, 10100)
        rid = resp.data['id']
        self.client.patch(f'/api/v1/vehicules/releves-km/{rid}/',
                          {'kilometrage': 10200, 'motif_correction': 'Faute de frappe'}, format='json')
        self.client.delete(f'/api/v1/vehicules/releves-km/{rid}/')
        journal = self.client.get('/api/v1/parametrage/corrections/', {'objet': rid}).data
        journal = journal.get('results', journal)
        self.assertEqual([j['action'] for j in journal], ['suppression', 'modification'])
        self.assertEqual(journal[1]['motif'], 'Faute de frappe')
        self.client.force_authenticate(self.operateur_b)
        res = self.client.get('/api/v1/parametrage/corrections/', {'objet': rid}).data
        self.assertEqual(len(res.get('results', res)), 0)
        self.client.force_authenticate(self.chauffeur)          # pas d'accès aux pleins ni relevés
        res = self.client.get('/api/v1/parametrage/corrections/').data
        self.assertEqual(len(res.get('results', res)), 0)

    def test_compteur_hors_formulaire_vehicule(self):
        # Le compteur passe par un relevé (contrôles de date et de compteur), pas par le formulaire
        self.client.force_authenticate(self.responsable_flotte)
        url = f'/api/v1/vehicules/{self.vehicule.id}/'
        resp = self.client.patch(url, {'kilometrage_actuel': 15000}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('relevé', str(resp.data['kilometrage_actuel']))
        # Renvoyer la valeur actuelle (formulaire complet) reste accepté
        resp = self.client.patch(url, {'kilometrage_actuel': self.km(), 'couleur': 'Blanc'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class ReferentielsCodeTests(UtilisateursMixin, APITestCase):
    """Catégories de dépense, types de sinistre et de contrat paramétrables."""

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def test_categorie_depense_parametrable_et_budget_par_poste(self):
        from apps.budget.models import BudgetAnnuel, DepenseVehicule
        from .models import CategorieDepense
        r = self.client.post('/api/v1/parametrage/categories-depense/',
                             {'code': 'lavage', 'libelle': 'Lavage', 'poste_budget': 'entretien'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post('/api/v1/budget/depenses/', {
            'agence': str(self.agence_a.id), 'categorie': 'lavage', 'date_depense': '2026-03-01',
            'montant': '5000', 'description': 'Lavage'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['categorie_display'], 'Lavage')
        DepenseVehicule.objects.create(agence=self.agence_a, categorie='assurance', date_depense='2026-03-02',
                                       montant=20000, description='Prime')
        b = BudgetAnnuel.objects.create(agence=self.agence_a, annee=2026)
        realise = self.client.get(f'/api/v1/budget/budgets/{b.id}/').data['realise']
        self.assertEqual(realise['entretien'], 5000.0)     # imputé sur le poste de la catégorie
        self.assertEqual(realise['assurances'], 20000.0)   # « assurance » → poste « assurances »
        # Code inconnu ou catégorie désactivée : refusé
        lavage = CategorieDepense.objects.get(code='lavage')
        self.client.patch(f'/api/v1/parametrage/categories-depense/{lavage.id}/', {'actif': False}, format='json')
        r = self.client.post('/api/v1/budget/depenses/', {
            'agence': str(self.agence_a.id), 'categorie': 'lavage', 'date_depense': '2026-03-01',
            'montant': '5000', 'description': 'Lavage'}, format='json')
        self.assertEqual(r.status_code, 400)
        # Utilisée : suppression refusée ; « carburant » (système) : ni suppression ni désactivation
        self.assertEqual(self.client.delete(f'/api/v1/parametrage/categories-depense/{lavage.id}/').status_code, 400)
        carb = CategorieDepense.objects.get(code='carburant')
        self.assertTrue(carb.systeme)
        self.assertEqual(self.client.delete(f'/api/v1/parametrage/categories-depense/{carb.id}/').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/parametrage/categories-depense/{carb.id}/',
                                           {'actif': False}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/parametrage/categories-depense/{carb.id}/',
                                           {'libelle': 'Gasoil & essence'}, format='json').status_code, 200)

    def test_types_sinistre_et_contrat(self):
        from apps.sinistres.models import Sinistre
        from .models import TypeContratAssurance, TypeSinistre
        self.assertTrue(TypeSinistre.objects.filter(code='bris_glace').exists())
        self.assertTrue(TypeContratAssurance.objects.filter(code='tous_risques').exists())
        r = self.client.post('/api/v1/parametrage/types-sinistre/', {'code': 'inondation', 'libelle': 'Inondation'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        v = Vehicule.objects.create(immatriculation='SN-1', agence=self.agence_a, annee=2020)
        s = Sinistre.objects.create(vehicule=v, agence=self.agence_a, type_sinistre='inondation',
                                    date_sinistre='2026-05-01', description='Crue')
        self.assertEqual(s.get_type_sinistre_display(), 'Inondation')
        t = TypeSinistre.objects.get(code='inondation')
        liste = self.client.get('/api/v1/parametrage/types-sinistre/').data
        self.assertEqual(next(x for x in liste if x['code'] == 'inondation')['nb_utilisations'], 1)
        self.assertEqual(self.client.delete(f'/api/v1/parametrage/types-sinistre/{t.id}/').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/parametrage/types-sinistre/{t.id}/', {'code': 'crue'},
                                           format='json').status_code, 400)
        r = self.client.patch(f'/api/v1/parametrage/types-sinistre/{t.id}/', {'libelle': 'Inondation / crue'},
                              format='json')
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.get_type_sinistre_display(), 'Inondation / crue')   # cache vidé

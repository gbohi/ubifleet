"""UbiFleet — Tests du workflow des demandes (droits et transitions)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionRole
from apps.accounts.permission_cache import invalidate
from apps.core.testing import UtilisateursMixin
from .models import Demande, LigneDemandeAchat, NiveauValidation, TypeDemande


class WorkflowDemandesTests(UtilisateursMixin, APITestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Circuit à 2 niveaux : gestionnaire puis responsable flotte
        cls.type = TypeDemande.objects.create(code='test', nom='Test', nb_niveaux=2)
        NiveauValidation.objects.create(type_demande=cls.type, niveau=1, libelle='Gestion',
                                        role_min=cls.roles['gestionnaire'])
        NiveauValidation.objects.create(type_demande=cls.type, niveau=2, libelle='Flotte',
                                        role_min=cls.roles['responsable_flotte'])

    def setUp(self):
        invalidate()

    def creer_demande(self, demandeur=None, statut=Demande.Statut.BROUILLON, niveau=1, type_=None):
        demandeur = demandeur or self.chauffeur
        return Demande.objects.create(
            type_demande=type_ or self.type, demandeur=demandeur, agence=demandeur.agence,
            titre='Pneus', description='Remplacement', statut=statut, niveau_actuel=niveau,
        )

    def url(self, demande, action=None):
        if action:
            return reverse(f'demande-{action}', args=[demande.id])
        return reverse('demande-detail', args=[demande.id])

    # ── Création et visibilité ────────────────────────────────────────
    def test_chauffeur_cree_une_demande(self):
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.post(reverse('demande-list'), {
            'type_demande': self.type.id, 'titre': 'Mission', 'description': 'Déplacement',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        d = Demande.objects.get(titre='Mission')
        self.assertEqual(d.demandeur, self.chauffeur)
        self.assertEqual(d.agence, self.agence_a)

    def test_demande_invisible_hors_agence(self):
        d = self.creer_demande()
        self.client.force_authenticate(self.operateur_b)
        self.assertEqual(self.client.get(self.url(d)).status_code, 404)
        self.assertEqual(self.client.delete(self.url(d)).status_code, 404)
        self.assertTrue(Demande.objects.filter(pk=d.pk).exists())

    def test_validateur_d_une_autre_agence_ne_voit_pas_la_demande(self):
        d = self.creer_demande(statut=Demande.Statut.SOUMISE)
        gest_b = self.creer_utilisateur('gest_b', 'gestionnaire', self.agence_b)
        self.client.force_authenticate(gest_b)
        self.assertEqual(self.client.get(self.url(d)).status_code, 404)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 404)
        self.assertEqual(self.client.get(reverse('demande-a-valider')).data, [])

    def test_validateur_toutes_agences(self):
        d = self.creer_demande(statut=Demande.Statut.SOUMISE)
        gest_global = self.creer_utilisateur('gest_global', 'gestionnaire', None)
        self.client.force_authenticate(gest_global)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 200)

    # ── Modification ──────────────────────────────────────────────────
    def test_seul_le_demandeur_modifie(self):
        d = self.creer_demande()
        self.client.force_authenticate(self.operateur)  # même agence
        resp = self.client.patch(self.url(d), {'titre': 'Piraté'}, format='json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.delete(self.url(d))
        self.assertEqual(resp.status_code, 403)
        d.refresh_from_db()
        self.assertEqual(d.titre, 'Pneus')

    def test_demandeur_modifie_son_brouillon(self):
        d = self.creer_demande()
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.patch(self.url(d), {'titre': 'Pneus AV'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_pas_de_modification_apres_soumission(self):
        d = self.creer_demande(statut=Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.patch(self.url(d), {'titre': 'Modifié'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.client.delete(self.url(d)).status_code, 400)

    def test_seul_le_demandeur_soumet(self):
        d = self.creer_demande()
        self.client.force_authenticate(self.operateur)
        self.assertEqual(self.client.post(self.url(d, 'soumettre')).status_code, 403)
        self.client.force_authenticate(self.chauffeur)
        self.assertEqual(self.client.post(self.url(d, 'soumettre')).status_code, 200)
        d.refresh_from_db()
        self.assertEqual(d.statut, Demande.Statut.SOUMISE)

    # ── Validation ────────────────────────────────────────────────────
    def test_circuit_complet(self):
        d = self.creer_demande(statut=Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 200)
        d.refresh_from_db()
        self.assertEqual((d.statut, d.niveau_actuel), (Demande.Statut.EN_VALIDATION, 2))

        # Le gestionnaire ne peut pas valider le niveau 2
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 403)

        self.client.force_authenticate(self.responsable_flotte)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 200)
        d.refresh_from_db()
        self.assertEqual(d.statut, Demande.Statut.APPROUVEE)

    def test_mauvais_role_ne_valide_pas(self):
        d = self.creer_demande(statut=Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.dg)  # niveau supérieur mais pas le rôle requis
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 403)

    def test_pas_d_auto_validation(self):
        d = self.creer_demande(demandeur=self.gestionnaire, statut=Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 403)
        resp = self.client.post(self.url(d, 'rejeter'), {'commentaire': 'non'}, format='json')
        self.assertEqual(resp.status_code, 403)
        d.refresh_from_db()
        self.assertEqual(d.statut, Demande.Statut.SOUMISE)

    def test_a_valider_exclut_ses_propres_demandes(self):
        self.creer_demande(demandeur=self.gestionnaire, statut=Demande.Statut.SOUMISE)
        autre = self.creer_demande(statut=Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.gestionnaire)
        resp = self.client.get(reverse('demande-a-valider'))
        self.assertEqual([x['id'] for x in resp.data], [str(autre.id)])

    def test_niveau_sans_role_reserve_au_super_admin(self):
        type_libre = TypeDemande.objects.create(code='libre', nom='Libre', nb_niveaux=1)
        NiveauValidation.objects.create(type_demande=type_libre, niveau=1, libelle='Libre')
        d = self.creer_demande(statut=Demande.Statut.SOUMISE, type_=type_libre)
        self.client.force_authenticate(self.operateur)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 403)
        self.client.force_authenticate(self.super_admin)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 200)

    def test_regle_db_valider_demande_appliquee(self):
        """Le nom d'action DRF « valider » correspond à « valider_demande » en DB."""
        PermissionRole.objects.create(role=self.roles['gestionnaire'], module='demandes',
                                      action='valider_demande', autorise=False)
        invalidate()
        d = self.creer_demande(statut=Demande.Statut.SOUMISE)
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.post(self.url(d, 'valider')).status_code, 403)

    # ── Lignes d'achat ────────────────────────────────────────────────
    def test_bulk_save_reserve_au_demandeur_en_brouillon(self):
        d = self.creer_demande()
        lignes = [{'designation': 'Pneu', 'quantite': 4, 'prix_unitaire': 50000}]
        payload = {'demande_id': str(d.id), 'lignes': lignes}

        self.client.force_authenticate(self.operateur)
        self.assertEqual(self.client.post(reverse('lignes-bulk-save'), payload, format='json').status_code, 403)
        self.client.force_authenticate(self.operateur_b)
        self.assertEqual(self.client.post(reverse('lignes-bulk-save'), payload, format='json').status_code, 404)

        self.client.force_authenticate(self.chauffeur)
        self.assertEqual(self.client.post(reverse('lignes-bulk-save'), payload, format='json').status_code, 200)
        d.refresh_from_db()
        self.assertEqual(d.montant_estime, 200000)

    def test_lignes_figees_apres_approbation(self):
        d = self.creer_demande(statut=Demande.Statut.APPROUVEE)
        ligne = LigneDemandeAchat.objects.create(demande=d, designation='Pneu', quantite=1, prix_unitaire=1000)
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.post(reverse('lignes-bulk-save'), {
            'demande_id': str(d.id), 'lignes': [{'designation': 'Pneu', 'quantite': 1, 'prix_unitaire': 999999}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.patch(reverse('ligne-detail', args=[ligne.id]), {'prix_unitaire': 999999}, format='json')
        self.assertEqual(resp.status_code, 400)
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_unitaire, 1000)

    def test_lignes_invisibles_hors_agence(self):
        d = self.creer_demande()
        LigneDemandeAchat.objects.create(demande=d, designation='Pneu', quantite=1)
        self.client.force_authenticate(self.operateur_b)
        resp = self.client.get(reverse('ligne-list'), {'demande': str(d.id)})
        self.assertEqual(resp.data, [])

    # ── Configuration du circuit ──────────────────────────────────────
    def test_configuration_reservee_au_super_admin(self):
        niveau = self.type.niveaux.get(niveau=1)
        self.client.force_authenticate(self.responsable_flotte)
        self.assertEqual(self.client.get(reverse('type-demande-list')).status_code, 200)
        resp = self.client.patch(reverse('niveau-detail', args=[niveau.id]),
                                 {'role_min': str(self.roles['chauffeur'].id)}, format='json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.patch(reverse('type-demande-detail', args=[self.type.id]),
                                 {'nb_niveaux': 1}, format='json')
        self.assertEqual(resp.status_code, 403)

        self.client.force_authenticate(self.super_admin)
        resp = self.client.patch(reverse('type-demande-detail', args=[self.type.id]),
                                 {'nb_niveaux': 1}, format='json')
        self.assertEqual(resp.status_code, 200)

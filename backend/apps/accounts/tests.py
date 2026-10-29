"""UbiFleet — Tests de sécurité des comptes (escalade de privilèges)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.parametrage.models import Parametre
from .models import Role, User


class SecuriteComptesTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(code='super_admin', nom='Super admin', niveau=10)
        cls.role_dg = Role.objects.create(code='dg', nom='DG', niveau=8)
        cls.role_flotte = Role.objects.create(code='responsable_flotte', nom='Resp. flotte', niveau=6)
        cls.role_gest = Role.objects.create(code='gestionnaire', nom='Gestionnaire', niveau=4)
        cls.role_chauffeur = Role.objects.create(code='chauffeur', nom='Chauffeur', niveau=1)

        cls.admin = cls._user('admin', cls.role_admin)
        cls.dg = cls._user('dg', cls.role_dg)
        cls.flotte = cls._user('flotte', cls.role_flotte)
        cls.gest = cls._user('gest', cls.role_gest)
        cls.chauffeur = cls._user('chauffeur', cls.role_chauffeur)

    @staticmethod
    def _user(nom, role):
        return User.objects.create_user(
            email=f'{nom}@test.ci', username=nom, password='Motdepasse!2026',
            first_name=nom, last_name='Test', role=role,
        )

    # ── /auth/me/ ─────────────────────────────────────────────────────
    def test_me_ne_permet_pas_de_changer_son_role(self):
        self.client.force_authenticate(self.chauffeur)
        url = reverse('me')
        for method in (self.client.patch, self.client.put):
            resp = method(url, {'role': str(self.role_admin.id)}, format='json')
            self.assertEqual(resp.status_code, 405)
        self.chauffeur.refresh_from_db()
        self.assertEqual(self.chauffeur.role, self.role_chauffeur)

    def test_me_lecture_ok(self):
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.get(reverse('me'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], 'chauffeur@test.ci')

    def test_profil_ignore_le_role(self):
        self.client.force_authenticate(self.chauffeur)
        resp = self.client.patch(
            reverse('reset_profile'),
            {'first_name': 'Nouveau', 'role': str(self.role_admin.id), 'is_active': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.chauffeur.refresh_from_db()
        self.assertEqual(self.chauffeur.first_name, 'Nouveau')
        self.assertEqual(self.chauffeur.role, self.role_chauffeur)
        self.assertTrue(self.chauffeur.is_active)

    # ── /auth/users/ ──────────────────────────────────────────────────
    def test_flotte_ne_peut_pas_se_promouvoir(self):
        self.client.force_authenticate(self.flotte)
        resp = self.client.patch(
            reverse('user-detail', args=[self.flotte.id]),
            {'role': str(self.role_admin.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.flotte.refresh_from_db()
        self.assertEqual(self.flotte.role, self.role_flotte)

    def test_flotte_ne_peut_pas_promouvoir_un_subordonne_au_dessus(self):
        self.client.force_authenticate(self.flotte)
        for role in (self.role_admin, self.role_dg, self.role_flotte):
            resp = self.client.patch(
                reverse('user-detail', args=[self.gest.id]),
                {'role': str(role.id)}, format='json',
            )
            self.assertEqual(resp.status_code, 400, role.code)
        self.gest.refresh_from_db()
        self.assertEqual(self.gest.role, self.role_gest)

    def test_flotte_peut_gerer_un_subordonne(self):
        self.client.force_authenticate(self.flotte)
        resp = self.client.patch(
            reverse('user-detail', args=[self.chauffeur.id]),
            {'role': str(self.role_gest.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.chauffeur.refresh_from_db()
        self.assertEqual(self.chauffeur.role, self.role_gest)

    def test_flotte_ne_peut_pas_creer_un_super_admin(self):
        self.client.force_authenticate(self.flotte)
        resp = self.client.post(reverse('user-list'), {
            'email': 'pirate@test.ci', 'username': 'pirate',
            'first_name': 'P', 'last_name': 'P',
            'password': 'Motdepasse!2026', 'password2': 'Motdepasse!2026',
            'role': str(self.role_admin.id),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(User.objects.filter(email='pirate@test.ci').exists())

    def test_flotte_ne_peut_pas_reinitialiser_le_mdp_du_super_admin(self):
        self.client.force_authenticate(self.flotte)
        resp = self.client.post(
            reverse('user-reset-password', args=[self.admin.id]),
            {'new_password': 'Piratage!2026'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('Motdepasse!2026'))

    def test_flotte_ne_peut_pas_desactiver_un_superieur(self):
        self.client.force_authenticate(self.flotte)
        resp = self.client.post(reverse('user-toggle-active', args=[self.dg.id]))
        self.assertEqual(resp.status_code, 403)
        self.dg.refresh_from_db()
        self.assertTrue(self.dg.is_active)

    def test_dg_peut_reinitialiser_un_subordonne(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.post(
            reverse('user-reset-password', args=[self.flotte.id]),
            {'new_password': 'Nouveau!2026'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_super_admin_peut_tout_attribuer(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            reverse('user-detail', args=[self.dg.id]),
            {'role': str(self.role_admin.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_gestionnaire_ne_gere_pas_les_utilisateurs(self):
        self.client.force_authenticate(self.gest)
        resp = self.client.patch(
            reverse('user-detail', args=[self.chauffeur.id]),
            {'role': str(self.role_gest.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

    # ── /parametrage/bulk_update/ ─────────────────────────────────────
    def test_bulk_update_parametres_refuse_sous_niveau_6(self):
        Parametre.objects.create(cle='alerte_ct_jours', valeur='30', type_valeur='int', categorie='alertes')
        self.client.force_authenticate(self.gest)
        resp = self.client.post('/api/v1/parametrage/bulk_update/',
                                [{'cle': 'alerte_ct_jours', 'valeur': '1'}], format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Parametre.objects.get(cle='alerte_ct_jours').valeur, '30')

    def test_bulk_update_parametres_ok_pour_flotte(self):
        Parametre.objects.create(cle='alerte_ct_jours', valeur='30', type_valeur='int', categorie='alertes')
        self.client.force_authenticate(self.flotte)
        resp = self.client.post('/api/v1/parametrage/bulk_update/',
                                [{'cle': 'alerte_ct_jours', 'valeur': '15'}], format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Parametre.objects.get(cle='alerte_ct_jours').valeur, '15')

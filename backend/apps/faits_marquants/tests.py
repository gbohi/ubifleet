"""UbiFleet — Tests des faits marquants (permissions, agences, document)."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionRole
from apps.accounts.permission_cache import invalidate
from apps.core.testing import UtilisateursMixin
from .models import FaitMarquant

MEDIA_TEST = '/tmp/claude-0/media-tests'


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class FaitsMarquantsTests(UtilisateursMixin, APITestCase):

    def setUp(self):
        invalidate()

    def creer(self, user, **extra):
        self.client.force_authenticate(user)
        data = {'libelle': 'Inondation dépôt', 'date': '2026-10-01', **extra}
        return self.client.post(reverse('fait-marquant-list'), data, format='multipart')

    def test_creation_avec_document(self):
        doc = SimpleUploadedFile('rapport.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        resp = self.creer(self.gestionnaire, document=doc)
        self.assertEqual(resp.status_code, 201, resp.data)
        fait = FaitMarquant.objects.get()
        self.assertEqual(fait.agence, self.agence_a)       # agence imposée
        self.assertEqual(resp.data['document_nom'], fait.document.name.split('/')[-1])

    def test_document_dangereux_refuse(self):
        doc = SimpleUploadedFile('page.html', b'<script>alert(1)</script>', content_type='text/html')
        resp = self.creer(self.gestionnaire, document=doc)
        self.assertEqual(resp.status_code, 400)

    def test_permissions_par_role(self):
        self.assertEqual(self.creer(self.operateur).status_code, 403)
        self.client.force_authenticate(self.chauffeur)
        self.assertEqual(self.client.get(reverse('fait-marquant-list')).status_code, 403)
        fait = FaitMarquant.objects.create(libelle='x', date='2026-01-01', agence=self.agence_a)
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.delete(reverse('fait-marquant-detail', args=[fait.id])).status_code, 403)

    def test_regle_configurable(self):
        PermissionRole.objects.create(role=self.roles['chauffeur'], module='faits_marquants',
                                      action='list', autorise=True)
        invalidate()
        self.client.force_authenticate(self.chauffeur)
        self.assertEqual(self.client.get(reverse('fait-marquant-list')).status_code, 200)

    def test_cloisonnement_agence(self):
        FaitMarquant.objects.create(libelle='Bouaké', date='2026-01-01', agence=self.agence_b)
        FaitMarquant.objects.create(libelle='Groupe', date='2026-01-02', agence=None)
        self.client.force_authenticate(self.operateur)
        libelles = [f['libelle'] for f in self.client.get(reverse('fait-marquant-list')).data['results']]
        self.assertEqual(libelles, ['Groupe'])
        # un fait « toutes agences » n'est pas modifiable par un utilisateur rattaché
        self.client.force_authenticate(self.responsable_flotte)
        fait = FaitMarquant.objects.get(libelle='Groupe')
        resp = self.client.patch(reverse('fait-marquant-detail', args=[fait.id]), {'libelle': 'y'}, format='json')
        self.assertEqual(resp.status_code, 403)

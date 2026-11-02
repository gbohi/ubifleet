"""UbiFleet — Tests Chauffeurs : documents, photo, archivage, contrôles de saisie."""

import datetime
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.core.testing import UtilisateursMixin
from .models import Chauffeur, DocumentChauffeur

MEDIA = tempfile.mkdtemp()


def png(nom='p.png'):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (10, 10), 'red').save(buf, 'PNG')
    return SimpleUploadedFile(nom, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=MEDIA)
class ChauffeurDocumentsTests(UtilisateursMixin, APITestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.c = Chauffeur.objects.create(matricule='CH-1', nom='Kone', prenom='Ali', numero_permis='P1',
                                         categories_permis='B', agence=cls.agence_a)

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def test_documents_envoi_controle_et_suppression(self):
        r = self.client.post('/api/v1/chauffeurs/documents/', {
            'chauffeur': str(self.c.id), 'type_document': 'visite_medicale', 'numero': 'VM-1',
            'date_expiration': '2026-01-31', 'fichier': SimpleUploadedFile('vm.pdf', b'%PDF-1.4 test', 'application/pdf')},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['type_document_libelle'], r.data['nom_fichier'], r.data['est_image']),
                         ('Visite médicale', 'vm.pdf', False))
        self.assertTrue(r.data['est_expire'])
        # Extension refusée, type inconnu
        r2 = self.client.post('/api/v1/chauffeurs/documents/', {
            'chauffeur': str(self.c.id), 'type_document': 'autre',
            'fichier': SimpleUploadedFile('x.exe', b'MZ', 'application/octet-stream')}, format='multipart')
        self.assertEqual(r2.status_code, 400)
        r3 = self.client.post('/api/v1/chauffeurs/documents/', {
            'chauffeur': str(self.c.id), 'type_document': 'inconnu', 'fichier': png()}, format='multipart')
        self.assertEqual(r3.status_code, 400)
        # Image acceptée ; liste filtrée par chauffeur ; compteur sur le chauffeur
        r4 = self.client.post('/api/v1/chauffeurs/documents/', {
            'chauffeur': str(self.c.id), 'type_document': 'identite', 'fichier': png('cni.png')}, format='multipart')
        self.assertTrue(r4.data['est_image'])
        self.assertEqual(len(self.client.get('/api/v1/chauffeurs/documents/', {'chauffeur': str(self.c.id)}).data), 2)
        c = self.client.get(f'/api/v1/chauffeurs/{self.c.id}/').data
        self.assertEqual((c['nb_documents'], c['documents_expires']), (2, 1))
        # Autre agence : invisible et refusé
        self.client.force_authenticate(self.operateur_b)
        self.assertEqual(self.client.get('/api/v1/chauffeurs/documents/').data, [])
        # Suppression
        self.client.force_authenticate(self.responsable_flotte)
        self.assertEqual(self.client.delete(f"/api/v1/chauffeurs/documents/{r.data['id']}/").status_code, 204)
        self.assertEqual(DocumentChauffeur.objects.count(), 1)

    def test_photo(self):
        r = self.client.post(f'/api/v1/chauffeurs/{self.c.id}/photo/', {'photo': png()}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['photo'])
        r = self.client.post(f'/api/v1/chauffeurs/{self.c.id}/photo/',
                             {'photo': SimpleUploadedFile('p.pdf', b'%PDF', 'application/pdf')}, format='multipart')
        self.assertEqual(r.status_code, 400)
        r = self.client.delete(f'/api/v1/chauffeurs/{self.c.id}/photo/')
        self.assertIsNone(r.data['photo'])

    def test_archivage_termine_les_affectations(self):
        from apps.vehicules.models import AffectationVehicule, Vehicule
        v = Vehicule.objects.create(immatriculation='CH-V1', agence=self.agence_a, annee=2020)
        AffectationVehicule.objects.create(vehicule=v, chauffeur=self.c, date_debut=datetime.date(2026, 1, 1))
        Vehicule.objects.filter(pk=v.pk).update(chauffeur_attitré=self.c)
        r = self.client.delete(f'/api/v1/chauffeurs/{self.c.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.c.refresh_from_db()
        v.refresh_from_db()
        self.assertEqual(self.c.statut, 'depart')
        self.assertIsNone(v.chauffeur_attitré)
        self.assertIsNotNone(AffectationVehicule.objects.get().date_fin)
        s = self.client.get('/api/v1/chauffeurs/stats/').data
        self.assertEqual((s['total'], s['par_statut']['depart']), (1, 1))

    def test_controles_saisie(self):
        Chauffeur.objects.create(matricule='CH-2', nom='Yao', prenom='Ben', numero_permis='P2', categories_permis='B',
                                 agence=self.agence_a, numero_chauffeur_total='0007')
        base = {'nom': 'N', 'prenom': 'P', 'numero_permis': 'X', 'categories_permis': 'B', 'agence': str(self.agence_a.id)}
        r = self.client.post('/api/v1/chauffeurs/', {**base, 'matricule': 'ch-1'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('déjà attribué', str(r.data['matricule']))
        r = self.client.post('/api/v1/chauffeurs/', {**base, 'matricule': 'CH-3', 'numero_chauffeur_total': '0007'}, format='json')
        self.assertIn('Ben Yao', str(r.data['numero_chauffeur_total']))
        r = self.client.post('/api/v1/chauffeurs/', {**base, 'matricule': 'CH-3', 'date_obtention_permis': '2020-01-01',
                                                     'date_expiration_permis': '2019-01-01'}, format='json')
        self.assertEqual(r.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA)
class AlertesDocumentsChauffeurTests(UtilisateursMixin, APITestCase):
    """Échéances visite médicale et contrat de travail (onglet Documents)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.c = Chauffeur.objects.create(matricule='AL-1', nom='Toure', prenom='Awa', numero_permis='P9',
                                         categories_permis='B', agence=cls.agence_a)

    def setUp(self):
        self.client.force_authenticate(self.responsable_flotte)

    def doc(self, type_document, jours):
        from django.utils import timezone
        r = self.client.post('/api/v1/chauffeurs/documents/', {
            'chauffeur': str(self.c.id), 'type_document': type_document,
            'date_expiration': (timezone.localdate() + datetime.timedelta(days=jours)).isoformat(),
            'fichier': SimpleUploadedFile('d.pdf', b'%PDF-1.4', 'application/pdf')}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def ouvertes(self):
        from apps.alertes.models import Alerte
        return Alerte.objects.filter(chauffeur=self.c, statut__in=['active', 'lue'])

    def test_visite_medicale_et_contrat(self):
        self.doc('visite_medicale', 5)          # seuil urgent (7 j) : priorité haute
        self.doc('contrat', -2)                 # expiré : critique
        self.doc('identite', -100)              # pas d'échéance pour ce type
        a = {x.type_alerte: x for x in self.ouvertes()}
        self.assertEqual(set(a), {'visite_med_exp', 'contrat_expire'})
        self.assertEqual((a['visite_med_exp'].priorite, a['contrat_expire'].priorite), ('haute', 'critique'))
        self.assertIn('J-5', a['visite_med_exp'].titre)
        # Contrat renouvelé : l'alerte se clôture (le document le plus récent compte)
        self.doc('contrat', 365)
        self.assertEqual(set(self.ouvertes().values_list('type_alerte', flat=True)), {'visite_med_exp'})
        # Chauffeur archivé : ses alertes documents se clôturent
        self.client.delete(f'/api/v1/chauffeurs/{self.c.id}/')
        self.assertFalse(self.ouvertes().exists())

    def test_seuil_parametrable_et_tache_globale(self):
        from apps.alertes.tasks import run_all_checks_sync
        from apps.parametrage.models import Parametre
        self.doc('visite_medicale', 45)                       # au-delà du seuil « attention » (30 j)
        self.assertFalse(self.ouvertes().exists())
        Parametre.objects.update_or_create(cle='echeance_visite_medicale_attention',
                                           defaults={'valeur': '60', 'type_valeur': 'int'})
        run_all_checks_sync()
        self.assertEqual(self.ouvertes().get().priorite, 'normale')

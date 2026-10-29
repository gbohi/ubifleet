"""UbiFleet — Tests Accounts"""

from django.test import TestCase
from .models import Agence
from .models import User


class TestAgence(TestCase):
    """Tests pour le modèle Agence."""

    def test_creation_agence(self):
        """Vérifie la création d'une agence"""
        agence = Agence.objects.create(nom='Test', code='TST', ville='Abidjan')
        self.assertEqual(str(agence), 'Test (TST)')

class TestUser(TestCase):
    """Tests pour le modèle User."""

    def test_creation_user(self):
        """Vérifie la création d'un utilisateur"""
        user = User.objects.create_user(email='test@ubipharm.ci', username='test', password='pass123')
        self.assertEqual(user.email, 'test@ubipharm.ci')


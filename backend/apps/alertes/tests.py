"""UbiFleet — Tests Alertes"""

from django.test import TestCase
from .models import Alerte


class TestAlerte(TestCase):
    """Tests pour le modèle Alerte."""

    def test_creation_alerte(self):
        """Vérifie la création d'une alerte"""
        # Test nécessite agence et fixtures
        pass


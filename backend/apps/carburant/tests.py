"""UbiFleet — Tests Carburant"""

from django.test import TestCase
from .models import PleinsCarburant


class TestPlein(TestCase):
    """Tests pour le modèle PleinsCarburant."""

    def test_calcul_consommation(self):
        """Vérifie le calcul automatique L/100km"""
        # Test nécessite vehicule et fixtures
        pass


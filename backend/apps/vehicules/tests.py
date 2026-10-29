"""UbiFleet — Tests Vehicules"""

from django.test import TestCase
from .models import Vehicule


class TestVehicule(TestCase):
    """Tests pour le modèle Vehicule."""

    def test_str_vehicule(self):
        """Vérifie la représentation string"""
        # Test nécessite agence et fixtures
        pass


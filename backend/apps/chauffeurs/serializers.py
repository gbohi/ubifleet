"""UbiFleet — Chauffeurs Serializers"""

from rest_framework import serializers
from .models import Chauffeur


class ChauffeurSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    permis_expire = serializers.BooleanField(read_only=True)
    jours_expiration_permis = serializers.IntegerField(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)
    vehicule_actuel = serializers.SerializerMethodField()

    class Meta:
        model = Chauffeur
        fields = [
            'id', 'matricule', 'nom', 'prenom', 'nom_complet',
            'date_naissance', 'telephone', 'email', 'adresse', 'photo',
            'numero_chauffeur_total', 'numero_permis', 'categories_permis',
            'date_obtention_permis', 'date_expiration_permis',
            'permis_expire', 'jours_expiration_permis',
            'agence', 'agence_nom', 'statut', 'statut_display',
            'vehicule_actuel', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_vehicule_actuel(self, obj):
        try:
            v = obj.vehicule_attitré
            if v is None:
                return None
            if hasattr(v, 'all'):
                v = v.first()
            if v is None:
                return None
            return {
                'id': str(v.id),
                'immatriculation': v.immatriculation,
                'designation': v.designation
            }
        except Exception:
            return None

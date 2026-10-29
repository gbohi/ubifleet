"""UbiFleet — Alertes Serializers"""

from rest_framework import serializers
from .models import Alerte


class AlerteSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_alerte_display', read_only=True)
    priorite_display = serializers.CharField(source='get_priorite_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    vehicule_immat = serializers.SerializerMethodField()
    chauffeur_nom = serializers.SerializerMethodField()
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)

    class Meta:
        model = Alerte
        fields = [
            'id', 'type_alerte', 'type_display',
            'priorite', 'priorite_display',
            'statut', 'statut_display',
            'titre', 'message',
            'vehicule', 'vehicule_immat',
            'chauffeur', 'chauffeur_nom',
            'agence', 'agence_nom',
            'date_echeance',
            'traitee_par', 'date_traitement', 'notes_traitement',
            'created_at'
        ]
        read_only_fields = ['created_at']

    def get_vehicule_immat(self, obj):
        return obj.vehicule.immatriculation if obj.vehicule else None

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

"""UbiFleet — Alertes Serializers"""

from rest_framework import serializers
from .models import Alerte


# Libellés de tous les types, y compris ceux créés hors de la liste du modèle
# (carte de transport, vignette).
LIBELLES_TYPES = {
    **dict(Alerte.TypeAlerte.choices),
    'carte_transport_exp':     'Carte de transport expirant bientôt',
    'carte_transport_expiree': 'Carte de transport expirée',
    'vignette_exp':            'Vignette expirant bientôt',
    'vignette_expiree':        'Vignette expirée',
}


class AlerteSerializer(serializers.ModelSerializer):
    type_display = serializers.SerializerMethodField()
    traitee_par_nom = serializers.SerializerMethodField()
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
            'plein', 'tournee_effectuee',
            'date_echeance',
            'traitee_par', 'traitee_par_nom', 'date_traitement', 'notes_traitement',
            'created_at'
        ]
        read_only_fields = ['created_at', 'plein', 'tournee_effectuee']

    def get_type_display(self, obj):
        return LIBELLES_TYPES.get(obj.type_alerte, obj.type_alerte)

    def get_traitee_par_nom(self, obj):
        u = obj.traitee_par
        return (u.get_full_name() or u.email) if u else None

    def get_vehicule_immat(self, obj):
        return obj.vehicule.immatriculation if obj.vehicule else None

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

"""UbiFleet — Sinistres Serializers"""

from rest_framework import serializers
from .models import Sinistre, ContratAssurance, Assureur, PieceJointeSinistre


class AssureurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assureur
        fields = ['id', 'nom', 'telephone', 'email', 'adresse', 'contact_sinistre', 'is_active']


class ContratAssuranceSerializer(serializers.ModelSerializer):
    assureur_nom = serializers.CharField(source='assureur.nom', read_only=True)
    vehicule_immat = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    est_expire = serializers.BooleanField(read_only=True)
    jours_restants = serializers.IntegerField(read_only=True)
    type_display = serializers.CharField(source='get_type_contrat_display', read_only=True)

    class Meta:
        model = ContratAssurance
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'assureur', 'assureur_nom',
            'numero_police', 'type_contrat', 'type_display',
            'date_debut', 'date_fin', 'prime_annuelle', 'franchise',
            'document', 'is_active', 'est_expire', 'jours_restants'
        ]


class PieceJointeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJointeSinistre
        fields = ['id', 'nom', 'fichier', 'type_document', 'created_at']


class SinistreSerializer(serializers.ModelSerializer):
    vehicule_immat = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    vehicule_designation = serializers.CharField(source='vehicule.designation', read_only=True)
    chauffeur_nom = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_type_sinistre_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)
    pièces_jointes = PieceJointeSerializer(many=True, read_only=True)

    class Meta:
        model = Sinistre
        fields = [
            'id', 'numero_dossier',
            'vehicule', 'vehicule_immat', 'vehicule_designation',
            'contrat_assurance', 'chauffeur', 'chauffeur_nom',
            'type_sinistre', 'type_display', 'statut', 'statut_display',
            'responsabilite', 'date_sinistre', 'lieu', 'description',
            'kilometrage_sinistre',
            'tiers_immatriculation', 'tiers_assureur', 'tiers_nom',
            'dommages_estimes', 'cout_reparation', 'indemnisation_recue',
            'franchise_appliquee',
            'date_declaration_assureur', 'date_expertise', 'date_cloture',
            'numero_constat',
            'agence', 'agence_nom', 'notes',
            'pièces_jointes', 'created_at'
        ]
        read_only_fields = ['numero_dossier', 'created_at']

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

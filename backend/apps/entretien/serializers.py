"""UbiFleet — Entretien Serializers"""

from rest_framework import serializers
from apps.core.referentiels import NbUtilisationsField
from .models import Intervention, TypeIntervention, Prestataire, SuiviPneus, DocumentIntervention


class TypeInterventionSerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)

    nb_utilisations = NbUtilisationsField()

    class Meta:
        model = TypeIntervention
        fields = [
            'id', 'nom', 'categorie', 'categorie_display',
            'periodicite_km', 'periodicite_mois', 'is_active', 'nb_utilisations'
        ]


class PrestataireSerializer(serializers.ModelSerializer):
    nb_utilisations = NbUtilisationsField()

    class Meta:
        model = Prestataire
        fields = [
            'id', 'nom', 'specialite', 'telephone', 'email',
            'adresse', 'ville', 'agence', 'note_qualite', 'is_active', 'nb_utilisations'
        ]


class InterventionSerializer(serializers.ModelSerializer):
    vehicule_immat = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    vehicule_designation = serializers.CharField(source='vehicule.designation', read_only=True)
    type_nom = serializers.CharField(source='type_intervention.nom', read_only=True)
    type_categorie = serializers.CharField(source='type_intervention.categorie', read_only=True)
    prestataire_nom = serializers.CharField(source='prestataire.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    priorite_display = serializers.CharField(source='get_priorite_display', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)

    class Meta:
        model = Intervention
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'vehicule_designation',
            'type_intervention', 'type_nom', 'type_categorie',
            'prestataire', 'prestataire_nom',
            'date_planifiee', 'date_debut', 'date_fin',
            'kilometrage_intervention', 'prochain_km',
            'cout_estime', 'cout_reel',
            'statut', 'statut_display', 'priorite', 'priorite_display',
            'description', 'rapport_intervention',
            'facture', 'bon_travail',
            'agence', 'agence_nom', 'created_at'
        ]
        read_only_fields = ['created_at']


class PneusSerializer(serializers.ModelSerializer):
    position_display = serializers.CharField(source='get_position_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    usure_pct = serializers.FloatField(read_only=True)
    kilometrage_utilise = serializers.IntegerField(read_only=True)
    vehicule_immat = serializers.CharField(source='vehicule.immatriculation', read_only=True)

    class Meta:
        model = SuiviPneus
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'position', 'position_display',
            'marque', 'dimension', 'date_montage', 'kilometrage_montage',
            'kilometrage_remplacement', 'statut', 'statut_display',
            'cout', 'usure_pct', 'kilometrage_utilise', 'notes'
        ]


class DocumentInterventionSerializer(serializers.ModelSerializer):
    fichier_url = serializers.SerializerMethodField()
    fichier_nom = serializers.SerializerMethodField()

    class Meta:
        model  = DocumentIntervention
        fields = ['id', 'intervention', 'fichier', 'fichier_url', 'fichier_nom',
                  'nom', 'type_doc', 'created_at']
        read_only_fields = ['created_at', 'fichier_url', 'fichier_nom']

    def get_fichier_url(self, obj):
        request = self.context.get('request')
        if obj.fichier and request:
            return request.build_absolute_uri(obj.fichier.url)
        return None

    def get_fichier_nom(self, obj):
        import os
        return os.path.basename(obj.fichier.name) if obj.fichier else ''

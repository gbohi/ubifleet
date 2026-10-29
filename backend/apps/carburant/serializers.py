"""UbiFleet — Carburant Serializers"""

from rest_framework import serializers
from django.utils import timezone
from .models import PleinsCarburant, DotationCarburant, Station, RapprochementCarburant


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = ['id', 'nom', 'ville', 'adresse', 'agence', 'est_partenaire', 'is_active']


class DotationSerializer(serializers.ModelSerializer):
    vehicule_immat = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    volume_consomme = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    taux_utilisation = serializers.FloatField(read_only=True)

    class Meta:
        model = DotationCarburant
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'mois', 'annee',
            'volume_alloue', 'volume_consomme', 'taux_utilisation', 'notes'
        ]


class PleinSerializer(serializers.ModelSerializer):
    vehicule_immat       = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    vehicule_designation = serializers.CharField(source='vehicule.designation', read_only=True)
    chauffeur_nom        = serializers.SerializerMethodField()
    station_nom          = serializers.CharField(source='station.nom', read_only=True)
    statut_display       = serializers.CharField(source='get_statut_validation_display', read_only=True)
    agence_nom           = serializers.CharField(source='agence.nom', read_only=True)
    tournee_libelle      = serializers.CharField(source='tournee.libelle', read_only=True, allow_null=True)
    tournee_code         = serializers.CharField(source='tournee.code',    read_only=True, allow_null=True)

    class Meta:
        model = PleinsCarburant
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'vehicule_designation',
            'chauffeur', 'chauffeur_nom', 'station', 'station_nom',
            'tournee', 'tournee_libelle', 'tournee_code',
            'date_plein', 'heure_plein', 'volume_litres', 'prix_litre', 'montant_fcfa',
            'kilometrage_releve', 'kilometrage_depart', 'consommation_calculee',
            'bon_carburant', 'photo_bon', 'photo_tableau_bord',
            'statut_validation', 'statut_display', 'motif_anomalie',
            'valide_par', 'date_validation',
            'agence', 'agence_nom', 'notes', 'created_at'
        ]
        read_only_fields = [
            'consommation_calculee', 'statut_validation', 'motif_anomalie',
            'valide_par', 'date_validation', 'created_at', 'kilometrage_depart',
        ]

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

    def validate(self, attrs):
        vehicule = attrs.get('vehicule') or self.instance.vehicule
        km = attrs.get('kilometrage_releve')
        if km and km < vehicule.kilometrage_actuel:
            raise serializers.ValidationError({
                'kilometrage_releve': "Le kilométrage est inférieur au kilométrage actuel du véhicule."
            })
        return attrs


class PleinValidationSerializer(serializers.Serializer):
    statut = serializers.ChoiceField(
        choices=[('valide', 'Validé'), ('rejete', 'Rejeté')]
    )
    motif = serializers.CharField(required=False, allow_blank=True)


class RapprochementSerializer(serializers.ModelSerializer):
    station_nom = serializers.CharField(source='station.nom', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)

    class Meta:
        model = RapprochementCarburant
        fields = [
            'id', 'agence', 'agence_nom', 'station', 'station_nom',
            'mois', 'annee', 'montant_facture', 'montant_saisi',
            'ecart', 'statut', 'fichier_facture', 'notes', 'created_at'
        ]
        read_only_fields = ['ecart', 'statut']

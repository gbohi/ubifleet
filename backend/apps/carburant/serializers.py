"""UbiFleet — Carburant Serializers"""

from rest_framework import serializers
from apps.parametrage.fenetre_saisie import CARBURANT, FenetreSaisieSerializerMixin
from apps.core.referentiels import NbUtilisationsField
from django.utils import timezone
from .models import PleinsCarburant, DotationCarburant, Station, RapprochementCarburant, PrixCarburant


class StationSerializer(serializers.ModelSerializer):
    agence_nom      = serializers.CharField(source='agence.nom', read_only=True, allow_null=True)
    nb_utilisations = NbUtilisationsField()

    class Meta:
        model = Station
        fields = ['id', 'nom', 'ville', 'adresse', 'agence', 'agence_nom', 'est_partenaire', 'is_active',
                  'nb_utilisations']


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


class PleinSerializer(FenetreSaisieSerializerMixin, serializers.ModelSerializer):
    domaine_saisie, champ_date = CARBURANT, 'date_plein'
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
            'agence', 'agence_nom', 'notes', 'created_at',
        ] + FenetreSaisieSerializerMixin.CHAMPS_FENETRE
        read_only_fields = [
            'consommation_calculee', 'statut_validation', 'motif_anomalie',
            'valide_par', 'date_validation', 'created_at', 'kilometrage_depart',
        ] + FenetreSaisieSerializerMixin.LECTURE_SEULE_FENETRE
        # Agence déduite du véhicule si elle n'est pas transmise
        extra_kwargs = {'agence': {'required': False}}

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

    def validate(self, attrs):
        # Contrôle par rapport aux saisies voisines, pas au compteur actuel :
        # une valeur trop élevée doit pouvoir être corrigée.
        from apps.vehicules.kilometrage import controler_km
        inst = self.instance
        # Heure obligatoire : elle ordonne les saisies d'une même journée.
        # Un plein ancien sans heure reste modifiable tant qu'on ne touche pas à ce champ.
        if (inst is None or 'heure_plein' in attrs) and not attrs.get('heure_plein'):
            raise serializers.ValidationError({'heure_plein': "L'heure du plein est obligatoire."})
        if (inst is None or 'tournee' in attrs) and not attrs.get('tournee'):
            raise serializers.ValidationError({'tournee': "La tournée est obligatoire."})
        controler_km(attrs.get('vehicule', inst and inst.vehicule),
                     attrs.get('kilometrage_releve', inst and inst.kilometrage_releve),
                     attrs.get('date_plein', inst and inst.date_plein),
                     'kilometrage_releve', exclure=inst,
                     heure=attrs.get('heure_plein', inst and inst.heure_plein))
        return attrs


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


class PrixCarburantSerializer(serializers.ModelSerializer):
    type_display   = serializers.CharField(source='get_type_carburant_display', read_only=True)
    created_by_nom = serializers.CharField(source='created_by.full_name', read_only=True, allow_null=True)

    class Meta:
        model  = PrixCarburant
        fields = ['id', 'type_carburant', 'type_display', 'prix', 'date_effet', 'commentaire',
                  'created_by', 'created_by_nom', 'created_at']
        read_only_fields = ['created_by', 'created_at']

    def validate_prix(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le prix doit être supérieur à 0.')
        return value

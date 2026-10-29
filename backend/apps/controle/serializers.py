"""UbiFleet — Contrôle Véhicule Serializers"""

from rest_framework import serializers
from .models import ElementControle, FicheControle, PointControleDetail, PhotoControle


class ElementControleSerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)

    class Meta:
        model  = ElementControle
        fields = ['id', 'nom', 'categorie', 'categorie_display', 'description',
                  'ordre', 'actif', 'obligatoire']


class PhotoControleSerializer(serializers.ModelSerializer):
    type_photo_display = serializers.CharField(source='get_type_photo_display', read_only=True)

    class Meta:
        model  = PhotoControle
        fields = ['id', 'fiche', 'image', 'type_photo', 'type_photo_display', 'legende', 'created_at']


class PointControleDetailSerializer(serializers.ModelSerializer):
    element_nom       = serializers.CharField(source='element.nom',      read_only=True)
    element_categorie = serializers.CharField(source='element.categorie', read_only=True)
    element_obligatoire = serializers.BooleanField(source='element.obligatoire', read_only=True)
    statut_display    = serializers.CharField(source='get_statut_display',  read_only=True)
    gravite_display   = serializers.CharField(source='get_gravite_display', read_only=True,
                                               allow_null=True)

    class Meta:
        model  = PointControleDetail
        fields = ['id', 'fiche', 'element', 'element_nom', 'element_categorie',
                  'element_obligatoire', 'statut', 'statut_display', 'gravite',
                  'gravite_display', 'remarque', 'photo_point']


class FicheControleListSerializer(serializers.ModelSerializer):
    vehicule_immat       = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    chauffeur_nom        = serializers.SerializerMethodField()
    agence_nom           = serializers.CharField(source='agence.nom', read_only=True, allow_null=True)
    type_controle_display= serializers.CharField(source='get_type_controle_display', read_only=True)
    statut_global_display= serializers.CharField(source='get_statut_global_display', read_only=True)
    nb_points            = serializers.SerializerMethodField()
    nb_non_conformes     = serializers.SerializerMethodField()
    nb_photos            = serializers.SerializerMethodField()

    class Meta:
        model  = FicheControle
        fields = ['id', 'vehicule', 'vehicule_immat', 'chauffeur', 'chauffeur_nom',
                  'agence', 'agence_nom', 'type_controle', 'type_controle_display',
                  'statut_global', 'statut_global_display', 'date_heure', 'kilometrage',
                  'nb_points', 'nb_non_conformes', 'nb_photos', 'created_at']

    def get_chauffeur_nom(self, obj):
        if obj.chauffeur:
            return f"{obj.chauffeur.prenom} {obj.chauffeur.nom}"
        return None

    def get_nb_points(self, obj):
        return obj.points.count()

    def get_nb_non_conformes(self, obj):
        return obj.points.filter(statut='non_conforme').count()

    def get_nb_photos(self, obj):
        return obj.photos.count()


class FicheControleDetailSerializer(FicheControleListSerializer):
    points = PointControleDetailSerializer(many=True, read_only=True)
    photos = PhotoControleSerializer(many=True, read_only=True)

    class Meta(FicheControleListSerializer.Meta):
        fields = FicheControleListSerializer.Meta.fields + [
            'notes_generales', 'signature_controleur', 'points', 'photos', 'updated_at'
        ]


class FicheControleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FicheControle
        fields = ['id', 'vehicule', 'chauffeur', 'agence', 'type_controle',
                  'date_heure', 'kilometrage', 'notes_generales']
        read_only_fields = ['id']

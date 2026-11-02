"""UbiFleet — Entretien Serializers"""

from django.utils import timezone
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
    vehicule_km = serializers.IntegerField(source='vehicule.kilometrage_actuel', read_only=True)
    en_retard = serializers.SerializerMethodField()
    nb_documents = serializers.SerializerMethodField()

    # Statuts modifiables par le formulaire ; « terminé » et « annulé » passent par
    # les actions terminer / annuler (coût réel, motif, statut du véhicule)
    STATUTS_FORMULAIRE = ('planifie', 'en_cours', 'attente_piece')

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
            'agence', 'agence_nom', 'created_at', 'vehicule_km', 'en_retard', 'nb_documents',
        ]
        # Agence : celle du véhicule (imposée à l'enregistrement)
        read_only_fields = ['created_at', 'agence']

    def get_en_retard(self, obj):
        return obj.statut == 'planifie' and obj.date_planifiee < timezone.localdate()

    def get_nb_documents(self, obj):
        return obj.documents.count()

    def validate_statut(self, value):
        if self.instance and self.instance.statut in ('termine', 'annule') and value != self.instance.statut:
            raise serializers.ValidationError(
                "Intervention terminée ou annulée : son statut ne se modifie plus.")
        if value not in self.STATUTS_FORMULAIRE and (not self.instance or value != self.instance.statut):
            raise serializers.ValidationError(
                "Pour terminer ou annuler l'intervention, utilisez les boutons « Clôturer » ou « Annuler » de sa fiche.")
        return value

    def validate_type_intervention(self, value):
        actuel = self.instance.type_intervention_id if self.instance else None
        if not value.is_active and value.pk != actuel:
            raise serializers.ValidationError(f"Type « {value.nom} » désactivé dans Paramètres.")
        return value

    def validate_prestataire(self, value):
        actuel = self.instance.prestataire_id if self.instance else None
        if value and not value.is_active and value.pk != actuel:
            raise serializers.ValidationError(f"Prestataire « {value.nom} » désactivé dans Paramètres.")
        return value

    def validate(self, attrs):
        for champ in ('cout_estime', 'cout_reel'):
            if attrs.get(champ) is not None and attrs[champ] < 0:
                raise serializers.ValidationError({champ: 'Le coût ne peut pas être négatif.'})
        debut = attrs.get('date_debut', getattr(self.instance, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({'date_fin': 'La date de fin précède la date de début.'})
        if self.instance and 'vehicule' in attrs and attrs['vehicule'] != self.instance.vehicule \
                and self.instance.statut in ('termine', 'annule'):
            raise serializers.ValidationError({'vehicule': "Intervention clôturée : le véhicule ne change plus."})
        return attrs


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

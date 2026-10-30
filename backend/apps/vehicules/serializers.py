"""UbiFleet — Véhicules Serializers"""

from rest_framework import serializers
from apps.parametrage.fenetre_saisie import RELEVES, FenetreSaisieSerializerMixin
from apps.accounts.serializers import AgenceSerializer
from .models import Vehicule, DocumentVehicule, TypeDocumentVehicule, ReleveKilometrage, HistoriqueImmatriculation, AffectationVehicule, HistoriqueStatutVehicule


class TypeDocumentVehiculeSerializer(serializers.ModelSerializer):
    nb_documents = serializers.SerializerMethodField()
    code = serializers.CharField(read_only=True)

    class Meta:
        model = TypeDocumentVehicule
        fields = ['id', 'code', 'libelle', 'actif', 'ordre', 'nb_documents']

    def get_nb_documents(self, obj):
        return obj.documents.count()


class DocumentVehiculeSerializer(serializers.ModelSerializer):
    type_document_code   = serializers.CharField(source='type_document.code',    read_only=True)
    type_document_libelle= serializers.CharField(source='type_document.libelle', read_only=True)
    type_display         = serializers.CharField(source='type_document.libelle', read_only=True)
    est_expire = serializers.BooleanField(read_only=True)

    class Meta:
        model = DocumentVehicule
        fields = [
            'id', 'type_document', 'type_document_code', 'type_document_libelle', 'type_display', 'numero',
            'date_emission', 'date_expiration', 'fichier',
            'est_expire', 'notes', 'created_at'
        ]


class VehiculeListSerializer(serializers.ModelSerializer):
    """Sérialiseur léger pour liste."""
    agence_detail = AgenceSerializer(source='agence', read_only=True)
    statut_display  = serializers.CharField(source='statut.libelle',  read_only=True, allow_null=True)
    marque_libelle  = serializers.CharField(source='marque.libelle',  read_only=True, allow_null=True)
    modele_libelle  = serializers.CharField(source='modele.libelle',  read_only=True, allow_null=True)
    statut_couleur  = serializers.CharField(source='statut.couleur', read_only=True, allow_null=True)
    affectation_libelle = serializers.CharField(source='affectation.libelle', read_only=True, allow_null=True)
    type_carburant_display = serializers.CharField(source='get_type_carburant_display', read_only=True)
    type_vehicule_display = serializers.CharField(source='get_type_vehicule_display', read_only=True)
    designation = serializers.CharField(read_only=True)
    revision_due = serializers.BooleanField(read_only=True)
    consommation_moyenne = serializers.SerializerMethodField()
    chauffeur_nom = serializers.SerializerMethodField()

    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'marque', 'marque_libelle', 'modele', 'modele_libelle', 'annee',
            'designation', 'type_vehicule', 'type_vehicule_display',
            'type_carburant', 'type_carburant_display',
            'statut', 'statut_display', 'statut_couleur', 'affectation_libelle',
            'agence', 'agence_detail',
            'kilometrage_actuel', 'conso_theorique_origine', 'kilometrage_revision', 'revision_due',
            'dotation_carburant_mensuelle',
            'valeur_acquisition',
            'chauffeur_attitré', 'chauffeur_nom',
            'photo', 'is_active', 'consommation_moyenne',
            'date_mise_en_service', 'created_at',
            'immatriculation_provisoire', 'est_immatriculation_provisoire',
            'date_immatriculation_definitive'
        ]

    def get_consommation_moyenne(self, obj):
        return obj.consommation_moyenne()

    def get_chauffeur_nom(self, obj):
        if obj.chauffeur_attitré:
            return obj.chauffeur_attitré.nom_complet
        return None


class VehiculeDetailSerializer(VehiculeListSerializer):
    """Sérialiseur complet avec documents."""
    documents = DocumentVehiculeSerializer(many=True, read_only=True)

    class Meta(VehiculeListSerializer.Meta):
        fields = VehiculeListSerializer.Meta.fields + [
            'numero_chassis', 'couleur', 'nombre_places',
            'affectation', 'date_acquisition', 'valeur_acquisition',
            'carte_grise', 'notes', 'documents', 'updated_at'
        ]


class VehiculeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicule
        exclude = ['created_at', 'updated_at', 'created_by']

    def validate_immatriculation(self, value):
        return value.upper().strip()

    def validate_kilometrage_actuel(self, value):
        if self.instance and value < self.instance.kilometrage_actuel:
            raise serializers.ValidationError(
                "Le kilométrage ne peut pas diminuer."
            )
        return value


class VehiculeKilometrageSerializer(serializers.Serializer):
    """Mise à jour rapide du kilométrage."""
    kilometrage = serializers.IntegerField(min_value=0)
    date_releve = serializers.DateField()

    def validate(self, attrs):
        vehicule = self.context['vehicule']
        if attrs['kilometrage'] < vehicule.kilometrage_actuel:
            raise serializers.ValidationError(
                "Le kilométrage saisi est inférieur au kilométrage actuel."
            )
        return attrs


class ReleveKilometrageSerializer(FenetreSaisieSerializerMixin, serializers.ModelSerializer):
    domaine_saisie, champ_date = RELEVES, 'date_releve'
    vehicule_immat       = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    vehicule_designation = serializers.CharField(source='vehicule.designation', read_only=True)
    type_display         = serializers.SerializerMethodField()
    type_couleur         = serializers.SerializerMethodField()
    chauffeur_nom        = serializers.SerializerMethodField()
    created_by_nom       = serializers.SerializerMethodField()
    photo_tableau_bord_url = serializers.SerializerMethodField()

    class Meta:
        model  = ReleveKilometrage
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'vehicule_designation',
            'kilometrage', 'date_releve', 'type_mouvement', 'type_display', 'type_couleur',
            'chauffeur', 'chauffeur_nom',
            'tournee', 'notes',
            'photo_tableau_bord', 'photo_tableau_bord_url',
            'created_by', 'created_by_nom', 'created_at',
        ] + FenetreSaisieSerializerMixin.CHAMPS_FENETRE
        read_only_fields = ['created_at', 'photo_tableau_bord_url'] + FenetreSaisieSerializerMixin.LECTURE_SEULE_FENETRE

    def _types(self):
        """Types de mouvement {code: objet}, chargés une fois par sérialisation."""
        if '_types_mouvement' not in self.context:
            from apps.parametrage.models import TypeMouvement
            self.context['_types_mouvement'] = {t.code: t for t in TypeMouvement.objects.all()}
        return self.context['_types_mouvement']

    def get_type_display(self, obj):
        t = self._types().get(obj.type_mouvement)
        return t.libelle if t else obj.type_mouvement

    def get_type_couleur(self, obj):
        t = self._types().get(obj.type_mouvement)
        return t.couleur if t else 'gray'

    def validate_type_mouvement(self, value):
        t = self._types().get(value)
        changement = self.instance is None or self.instance.type_mouvement != value
        if t is None or (changement and not t.actif):
            raise serializers.ValidationError("Type de mouvement inconnu ou désactivé.")
        return value

    def get_chauffeur_nom(self, obj):
        if obj.chauffeur:
            return f"{obj.chauffeur.prenom} {obj.chauffeur.nom}".strip()
        return None

    def get_created_by_nom(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None

    def get_photo_tableau_bord_url(self, obj):
        request = self.context.get('request')
        if obj.photo_tableau_bord and request:
            return request.build_absolute_uri(obj.photo_tableau_bord.url)
        return None


class HistoriqueImmatriculationSerializer(serializers.ModelSerializer):
    created_by_nom = serializers.SerializerMethodField()

    class Meta:
        model = HistoriqueImmatriculation
        fields = [
            'id', 'vehicule', 'ancienne_immatriculation',
            'nouvelle_immatriculation', 'date_changement',
            'motif', 'created_by', 'created_by_nom', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_created_by_nom(self, obj):
        if obj.created_by:
            return (
                f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
                or obj.created_by.username
            )
        return None


class AffectationVehiculeSerializer(serializers.ModelSerializer):
    vehicule_immat       = serializers.CharField(source='vehicule.immatriculation', read_only=True)
    vehicule_designation = serializers.CharField(source='vehicule.designation', read_only=True)
    chauffeur_nom        = serializers.SerializerMethodField()
    est_active           = serializers.BooleanField(read_only=True)
    created_by_nom       = serializers.SerializerMethodField()

    class Meta:
        model  = AffectationVehicule
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'vehicule_designation',
            'chauffeur', 'chauffeur_nom',
            'date_debut', 'date_fin', 'notes',
            'est_active', 'created_by', 'created_by_nom',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_chauffeur_nom(self, obj):
        return f"{obj.chauffeur.prenom} {obj.chauffeur.nom}".strip()

    def get_created_by_nom(self, obj):
        if obj.created_by:
            return (
                f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
                or obj.created_by.username
            )
        return None


class HistoriqueStatutVehiculeSerializer(serializers.ModelSerializer):
    ancien_statut_libelle  = serializers.CharField(source='ancien_statut.libelle',  read_only=True, allow_null=True)
    nouveau_statut_libelle = serializers.CharField(source='nouveau_statut.libelle', read_only=True, allow_null=True)
    nouveau_statut_couleur = serializers.CharField(source='nouveau_statut.couleur', read_only=True, allow_null=True)
    created_by_nom         = serializers.SerializerMethodField()

    class Meta:
        model  = HistoriqueStatutVehicule
        fields = [
            'id', 'vehicule', 'ancien_statut', 'ancien_statut_libelle',
            'nouveau_statut', 'nouveau_statut_libelle', 'nouveau_statut_couleur',
            'motif', 'date_changement', 'created_by', 'created_by_nom', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_created_by_nom(self, obj):
        if obj.created_by:
            return (f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
                    or obj.created_by.username)
        return None

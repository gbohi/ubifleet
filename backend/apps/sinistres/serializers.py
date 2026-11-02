"""UbiFleet — Sinistres Serializers"""

from rest_framework import serializers
from apps.core.referentiels import NbUtilisationsField, valider_code_referentiel
from .models import Sinistre, ContratAssurance, Assureur, PieceJointeSinistre


class AssureurSerializer(serializers.ModelSerializer):
    nb_utilisations = NbUtilisationsField()

    class Meta:
        model = Assureur
        fields = ['id', 'nom', 'telephone', 'email', 'adresse', 'contact_sinistre', 'is_active', 'nb_utilisations']


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

    def validate(self, attrs):
        debut = attrs.get('date_debut', getattr(self.instance, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
        if debut and fin and fin <= debut:
            raise serializers.ValidationError({'date_fin': 'La date de fin doit suivre la date de début.'})
        for champ in ('prime_annuelle', 'franchise'):
            if attrs.get(champ) is not None and attrs[champ] < 0:
                raise serializers.ValidationError({champ: 'Le montant ne peut pas être négatif.'})
        return attrs

    def validate_type_contrat(self, value):
        from apps.parametrage.models import TypeContratAssurance
        return valider_code_referentiel(TypeContratAssurance, value,
                                        self.instance.type_contrat if self.instance else None,
                                        'Type de contrat')


class PieceJointeSerializer(serializers.ModelSerializer):
    type_document_display = serializers.CharField(source='get_type_document_display', read_only=True)
    est_image = serializers.SerializerMethodField()

    class Meta:
        model = PieceJointeSinistre
        fields = ['id', 'sinistre', 'nom', 'fichier', 'type_document', 'type_document_display', 'est_image', 'created_at']
        extra_kwargs = {'nom': {'required': False, 'allow_blank': True}}

    def get_est_image(self, obj):
        return bool(obj.fichier) and obj.fichier.name.lower().rsplit('.', 1)[-1] in ('jpg', 'jpeg', 'png', 'webp')

    def validate(self, attrs):
        if not attrs.get('nom') and attrs.get('fichier'):
            attrs['nom'] = attrs['fichier'].name[:100]
        return attrs


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
            'pièces_jointes', 'created_at', 'reste_a_charge', 'contrat_libelle',
        ]
        # Agence : celle du véhicule (imposée à l'enregistrement)
        read_only_fields = ['numero_dossier', 'created_at', 'agence', 'statut', 'date_cloture']

    reste_a_charge = serializers.SerializerMethodField()
    contrat_libelle = serializers.SerializerMethodField()

    def get_reste_a_charge(self, obj):
        if obj.cout_reparation is None:
            return None
        return max(float(obj.cout_reparation) - float(obj.indemnisation_recue or 0), 0)

    def get_contrat_libelle(self, obj):
        c = obj.contrat_assurance
        return f"{c.assureur.nom} — {c.numero_police} ({c.get_type_contrat_display()})" if c else None

    def validate(self, attrs):
        from django.utils import timezone
        g = lambda k: attrs.get(k, getattr(self.instance, k, None))
        vehicule, contrat, chauffeur = g('vehicule'), g('contrat_assurance'), g('chauffeur')
        if g('date_sinistre') and g('date_sinistre') > timezone.localdate():
            raise serializers.ValidationError({'date_sinistre': 'La date du sinistre ne peut pas être dans le futur.'})
        for champ in ('date_declaration_assureur', 'date_expertise'):
            if g(champ) and g('date_sinistre') and g(champ) < g('date_sinistre'):
                raise serializers.ValidationError({champ: 'Cette date précède celle du sinistre.'})
        if contrat and vehicule and contrat.vehicule_id != vehicule.pk:
            raise serializers.ValidationError({'contrat_assurance': "Ce contrat d'assurance couvre un autre véhicule."})
        if chauffeur and vehicule and chauffeur.agence_id != vehicule.agence_id:
            raise serializers.ValidationError({'chauffeur': "Ce chauffeur n'est pas de l'agence du véhicule."})
        for champ in ('dommages_estimes', 'cout_reparation', 'indemnisation_recue', 'franchise_appliquee'):
            if attrs.get(champ) is not None and attrs[champ] < 0:
                raise serializers.ValidationError({champ: 'Le montant ne peut pas être négatif.'})
        return attrs

    def validate_type_sinistre(self, value):
        from apps.parametrage.models import TypeSinistre
        return valider_code_referentiel(TypeSinistre, value,
                                        self.instance.type_sinistre if self.instance else None,
                                        'Type de sinistre')

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

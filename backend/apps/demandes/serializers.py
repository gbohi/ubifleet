"""UbiFleet — Demandes Serializers"""

from rest_framework import serializers
from .models import TypeDemande, NiveauValidation, Demande, ValidationDemande, LigneDemandeAchat


class NiveauValidationSerializer(serializers.ModelSerializer):
    role_nom = serializers.SerializerMethodField()

    class Meta:
        model  = NiveauValidation
        fields = ['id', 'type_demande', 'niveau', 'libelle', 'role_min', 'role_nom']

    def get_role_nom(self, obj):
        if obj.role_min:
            return obj.role_min.nom
        return None


class TypeDemandeSerializer(serializers.ModelSerializer):
    code_display = serializers.CharField(source='code', read_only=True)
    niveaux      = NiveauValidationSerializer(many=True, read_only=True)

    class Meta:
        model  = TypeDemande
        fields = ['id', 'code', 'code_display', 'nom', 'description',
                  'nb_niveaux', 'actif', 'delai_reponse_jours', 'niveaux']


class ValidationDemandeSerializer(serializers.ModelSerializer):
    validateur_nom   = serializers.SerializerMethodField()
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)

    class Meta:
        model  = ValidationDemande
        fields = ['id', 'niveau', 'validateur', 'validateur_nom',
                  'decision', 'decision_display', 'commentaire', 'date_decision']

    def get_validateur_nom(self, obj):
        if obj.validateur:
            return (f"{obj.validateur.first_name} {obj.validateur.last_name}".strip()
                    or obj.validateur.username)
        return None


class LigneDemandeAchatSerializer(serializers.ModelSerializer):
    montant_ligne = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, allow_null=True
    )

    class Meta:
        model  = LigneDemandeAchat
        fields = ['id', 'demande', 'designation', 'quantite', 'unite',
                  'prix_unitaire', 'fournisseur', 'notes', 'ordre', 'montant_ligne']


class DemandeListSerializer(serializers.ModelSerializer):
    type_nom         = serializers.CharField(source='type_demande.nom', read_only=True)
    type_code        = serializers.CharField(source='type_demande.code', read_only=True)
    demandeur_nom    = serializers.SerializerMethodField()
    agence_nom       = serializers.CharField(source='agence.nom', read_only=True, allow_null=True)
    vehicule_immat   = serializers.CharField(source='vehicule.immatriculation',
                                              read_only=True, allow_null=True)
    statut_display   = serializers.CharField(source='get_statut_display', read_only=True)
    priorite_display = serializers.CharField(source='get_priorite_display', read_only=True)
    nb_niveaux_total = serializers.IntegerField(source='type_demande.nb_niveaux', read_only=True)
    progression_pct  = serializers.SerializerMethodField()
    total_achat      = serializers.SerializerMethodField()
    nb_lignes        = serializers.SerializerMethodField()

    class Meta:
        model  = Demande
        fields = ['id', 'numero', 'titre', 'type_nom', 'type_code',
                  'demandeur', 'demandeur_nom', 'agence', 'agence_nom',
                  'statut', 'statut_display', 'priorite', 'priorite_display',
                  'niveau_actuel', 'nb_niveaux_total', 'progression_pct',
                  'vehicule', 'vehicule_immat', 'date_souhaitee',
                  'montant_estime', 'total_achat', 'nb_lignes', 'created_at']

    def get_demandeur_nom(self, obj):
        u = obj.demandeur
        return f"{u.first_name} {u.last_name}".strip() or u.username

    def get_progression_pct(self, obj):
        total = obj.type_demande.nb_niveaux
        if obj.statut == 'approuvee': return 100
        if obj.statut in ['rejetee', 'annulee', 'brouillon']: return 0
        if total == 0: return 0
        return round(((obj.niveau_actuel - 1) / total) * 100)

    def get_total_achat(self, obj):
        total = 0
        for l in obj.lignes_achat.all():
            if l.prix_unitaire:
                total += float(l.quantite) * float(l.prix_unitaire)
        return total or None

    def get_nb_lignes(self, obj):
        return obj.lignes_achat.count()


class DemandeDetailSerializer(DemandeListSerializer):
    validations  = ValidationDemandeSerializer(many=True, read_only=True)
    lignes_achat = LigneDemandeAchatSerializer(many=True, read_only=True)

    class Meta(DemandeListSerializer.Meta):
        fields = DemandeListSerializer.Meta.fields + [
            'description', 'materiel', 'quantite', 'unite',
            'fournisseur_suggere', 'fichier_joint', 'chauffeur',
            'date_traitement', 'validations', 'lignes_achat',
            'notes_internes', 'updated_at'
        ]


class DemandeWriteSerializer(serializers.ModelSerializer):
    # Types créés automatiquement par d'autres écrans (ex. dotation de tournée)
    TYPES_AUTOMATIQUES = ('dotation',)

    def validate_type_demande(self, value):
        if value and value.code in self.TYPES_AUTOMATIQUES:
            raise serializers.ValidationError(
                "Ce type de demande se crée depuis son écran dédié (ex. Paramètres › Tournées).")
        return value

    class Meta:
        model  = Demande
        fields = ['id', 'type_demande', 'titre', 'description', 'priorite',
                  'date_souhaitee', 'vehicule', 'chauffeur', 'agence',
                  'materiel', 'quantite', 'unite', 'fournisseur_suggere',
                  'montant_estime', 'fichier_joint']
        read_only_fields = ['id']

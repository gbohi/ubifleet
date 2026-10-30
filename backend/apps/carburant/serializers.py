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
    type_display         = serializers.SerializerMethodField()
    type_couleur         = serializers.SerializerMethodField()
    tournee_effectuee_numero = serializers.CharField(source='tournee_effectuee.numero', read_only=True,
                                                     allow_null=True)
    tournee_effectuee_statut = serializers.CharField(source='tournee_effectuee.statut', read_only=True,
                                                     allow_null=True)
    # « Dernière prise de cette tournée » : clôture la tournée à l'enregistrement
    cloturer_tournee     = serializers.BooleanField(write_only=True, required=False, default=False)
    commentaire_tournee  = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = PleinsCarburant
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'vehicule_designation',
            'chauffeur', 'chauffeur_nom', 'station', 'station_nom',
            'type_mouvement', 'type_display', 'type_couleur',
            'tournee', 'tournee_libelle', 'tournee_code',
            'tournee_effectuee', 'tournee_effectuee_numero', 'tournee_effectuee_statut',
            'cloturer_tournee', 'commentaire_tournee',
            'date_plein', 'heure_plein', 'volume_litres', 'prix_litre', 'montant_fcfa',
            'kilometrage_releve', 'kilometrage_depart', 'consommation_calculee',
            'bon_carburant', 'photo_bon', 'photo_tableau_bord',
            'statut_validation', 'statut_display', 'motif_anomalie',
            'valide_par', 'date_validation',
            'agence', 'agence_nom', 'notes', 'created_at',
        ] + FenetreSaisieSerializerMixin.CHAMPS_FENETRE
        read_only_fields = [
            'consommation_calculee', 'statut_validation', 'motif_anomalie',
            'valide_par', 'date_validation', 'created_at', 'kilometrage_depart', 'tournee_effectuee',
        ] + FenetreSaisieSerializerMixin.LECTURE_SEULE_FENETRE
        # Agence déduite du véhicule si elle n'est pas transmise
        extra_kwargs = {'agence': {'required': False}}

    def get_chauffeur_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else None

    def _types(self):
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
        if t is None or (changement and not (t.actif and t.pour_prises)):
            raise serializers.ValidationError(
                "Type de mouvement inconnu, désactivé ou non prévu pour les prises de carburant.")
        return value

    def validate(self, attrs):
        # Contrôle par rapport aux saisies voisines, pas au compteur actuel :
        # une valeur trop élevée doit pouvoir être corrigée.
        from apps.parametrage.models import TypeMouvement
        from apps.vehicules.kilometrage import controler_km
        from .tournees import en_cours, quand
        TOURNEE = TypeMouvement.CODE_TOURNEE
        inst = self.instance
        # Heure obligatoire : elle ordonne les saisies d'une même journée.
        # Une prise ancienne sans heure reste modifiable tant qu'on ne touche pas à ce champ.
        if (inst is None or 'heure_plein' in attrs) and not attrs.get('heure_plein'):
            raise serializers.ValidationError({'heure_plein': "L'heure de la prise de carburant est obligatoire."})
        if inst is None and not attrs.get('type_mouvement'):
            raise serializers.ValidationError({'type_mouvement': "Le type de mouvement est obligatoire."})
        type_mvt = attrs.get('type_mouvement', inst and inst.type_mouvement)
        vehicule = attrs.get('vehicule', inst and inst.vehicule)

        if inst is None:
            # Véhicule en tournée : la prise est rattachée à cette tournée
            te = en_cours(vehicule)
            if te:
                if type_mvt != TOURNEE:
                    raise serializers.ValidationError({'type_mouvement': (
                        f"Le véhicule est en tournée {te.tournee.code} (n° {te.numero}) depuis le "
                        f"{quand(te.date_debut, te.heure_debut)} : la prise lui est rattachée. Clôturez "
                        "cette tournée pour saisir une prise d'un autre type.")})
                if attrs.get('tournee') and attrs['tournee'] != te.tournee:
                    raise serializers.ValidationError({'tournee': (
                        f"Le véhicule est en tournée {te.tournee.code} (n° {te.numero}) : clôturez-la "
                        "avant d'en commencer une autre.")})
                attrs['tournee'] = te.tournee
                attrs['tournee_effectuee'] = te
        else:
            te = inst.tournee_effectuee
            if te:
                if type_mvt != TOURNEE or attrs.get('tournee', te.tournee) != te.tournee \
                        or vehicule != te.vehicule:
                    raise serializers.ValidationError({'type_mouvement': (
                        f"Cette prise appartient à la tournée n° {te.numero} : son véhicule, son type et "
                        "sa tournée ne peuvent pas changer. Supprimez-la et ressaisissez-la si besoin.")})
            elif type_mvt == TOURNEE and inst.type_mouvement != TOURNEE:
                raise serializers.ValidationError({'type_mouvement': (
                    "Une prise existante ne peut pas être rattachée à une tournée : supprimez-la et "
                    "ressaisissez-la avec le type « Tournée ».")})
        if type_mvt == TOURNEE:
            # À la création, ou si le type ou la tournée sont modifiés
            if (inst is None or 'type_mouvement' in attrs or 'tournee' in attrs) \
                    and not attrs.get('tournee', inst and inst.tournee):
                raise serializers.ValidationError({'tournee': "La tournée est obligatoire pour ce type de mouvement."})
        else:
            attrs['tournee'] = None
            if attrs.get('cloturer_tournee'):
                attrs['cloturer_tournee'] = False

        controler_km(vehicule,
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

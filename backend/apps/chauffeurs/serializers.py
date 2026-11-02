"""UbiFleet — Chauffeurs Serializers"""

import os

from rest_framework import serializers
from apps.core.referentiels import valider_code_referentiel
from .models import Chauffeur, DocumentChauffeur


class ChauffeurSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    permis_expire = serializers.BooleanField(read_only=True)
    jours_expiration_permis = serializers.IntegerField(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)
    vehicule_actuel = serializers.SerializerMethodField()

    class Meta:
        model = Chauffeur
        fields = [
            'id', 'matricule', 'nom', 'prenom', 'nom_complet',
            'date_naissance', 'telephone', 'email', 'adresse', 'photo',
            'numero_chauffeur_total', 'numero_permis', 'categories_permis',
            'date_obtention_permis', 'date_expiration_permis',
            'permis_expire', 'jours_expiration_permis',
            'agence', 'agence_nom', 'statut', 'statut_display',
            'vehicule_actuel', 'notes', 'created_at', 'nb_documents', 'documents_expires',
        ]
        # Photo : envoyée par /chauffeurs/{id}/photo/ (multipart)
        read_only_fields = ['created_at', 'photo']

    nb_documents = serializers.SerializerMethodField()
    documents_expires = serializers.SerializerMethodField()

    def get_nb_documents(self, obj):
        return len(obj.documents.all())

    def get_documents_expires(self, obj):
        from django.utils import timezone
        return sum(1 for d in obj.documents.all() if d.date_expiration and d.date_expiration < timezone.localdate())

    def validate_matricule(self, value):
        value = value.strip().upper()
        qs = Chauffeur.objects.filter(matricule__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"Le matricule « {value} » est déjà attribué à un autre chauffeur.")
        return value

    def validate_statut(self, value):
        if value == Chauffeur.Statut.DEPART and (not self.instance or self.instance.statut != value):
            raise serializers.ValidationError(
                "Pour un départ, utilisez « Archiver » dans la liste des chauffeurs : ses affectations en cours "
                "sont alors terminées.")
        return value

    def validate_numero_chauffeur_total(self, value):
        """Unique : il relie les transactions Total au chauffeur."""
        value = (value or '').strip()
        if value:
            qs = Chauffeur.objects.filter(numero_chauffeur_total=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            autre = qs.first()
            if autre:
                raise serializers.ValidationError(
                    f"N° chauffeur Total déjà attribué à {autre.nom_complet} ({autre.matricule}).")
        return value

    def validate(self, attrs):
        ob = attrs.get('date_obtention_permis', getattr(self.instance, 'date_obtention_permis', None))
        ex = attrs.get('date_expiration_permis', getattr(self.instance, 'date_expiration_permis', None))
        if ob and ex and ex <= ob:
            raise serializers.ValidationError({'date_expiration_permis':
                "La date d'expiration du permis doit être postérieure à sa date d'obtention."})
        return attrs

    def get_vehicule_actuel(self, obj):
        try:
            v = obj.vehicule_attitré
            if v is None:
                return None
            if hasattr(v, 'all'):
                v = v.first()
            if v is None:
                return None
            return {
                'id': str(v.id),
                'immatriculation': v.immatriculation,
                'designation': v.designation
            }
        except Exception:
            return None


class DocumentChauffeurSerializer(serializers.ModelSerializer):
    type_document_libelle = serializers.CharField(source='get_type_document_display', read_only=True)
    est_expire = serializers.BooleanField(read_only=True)
    jours_restants = serializers.IntegerField(read_only=True)
    nom_fichier = serializers.SerializerMethodField()
    taille = serializers.SerializerMethodField()
    est_image = serializers.SerializerMethodField()
    ajoute_par = serializers.SerializerMethodField()

    class Meta:
        model = DocumentChauffeur
        fields = ['id', 'chauffeur', 'type_document', 'type_document_libelle', 'libelle', 'numero',
                  'date_emission', 'date_expiration', 'est_expire', 'jours_restants', 'fichier',
                  'nom_fichier', 'taille', 'est_image', 'notes', 'ajoute_par', 'created_at']
        read_only_fields = ['created_at']

    def validate_type_document(self, value):
        from apps.parametrage.models import TypeDocumentChauffeur
        return valider_code_referentiel(TypeDocumentChauffeur, value,
                                        self.instance.type_document if self.instance else None, 'Type de document')

    def validate(self, attrs):
        em = attrs.get('date_emission', getattr(self.instance, 'date_emission', None))
        ex = attrs.get('date_expiration', getattr(self.instance, 'date_expiration', None))
        if em and ex and ex < em:
            raise serializers.ValidationError({'date_expiration': "La date d'expiration précède la date d'émission."})
        if self.instance and 'chauffeur' in attrs and attrs['chauffeur'] != self.instance.chauffeur:
            raise serializers.ValidationError({'chauffeur': "Un document ne change pas de chauffeur."})
        return attrs

    def get_nom_fichier(self, obj):
        return os.path.basename(obj.fichier.name) if obj.fichier else None

    def get_taille(self, obj):
        try:
            return obj.fichier.size if obj.fichier else None
        except (FileNotFoundError, OSError):
            return None

    def get_est_image(self, obj):
        return bool(obj.fichier) and obj.fichier.name.lower().rsplit('.', 1)[-1] in ('jpg', 'jpeg', 'png', 'webp')

    def get_ajoute_par(self, obj):
        u = obj.created_by
        return (u.get_full_name() or u.email) if u else None

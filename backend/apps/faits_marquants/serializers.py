"""UbiFleet — Faits marquants : sérialiseurs."""
import os

from rest_framework import serializers

from .models import FaitMarquant


class FaitMarquantSerializer(serializers.ModelSerializer):
    agence_nom     = serializers.CharField(source='agence.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(source='created_by.full_name', read_only=True, allow_null=True)
    document_nom   = serializers.SerializerMethodField()

    class Meta:
        model  = FaitMarquant
        fields = ['id', 'libelle', 'date', 'description', 'document', 'document_nom',
                  'agence', 'agence_nom', 'created_by_nom', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_libelle(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le libellé est obligatoire.")
        return value

    def update(self, instance, validated_data):
        # Document remplacé ou retiré : l'ancien fichier est supprimé du disque
        if 'document' in validated_data and instance.document \
                and validated_data['document'] != instance.document:
            instance.document.delete(save=False)
        return super().update(instance, validated_data)

    def get_document_nom(self, obj) -> str | None:
        return os.path.basename(obj.document.name) if obj.document else None

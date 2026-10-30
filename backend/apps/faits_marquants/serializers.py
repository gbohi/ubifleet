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

    def get_document_nom(self, obj) -> str | None:
        return os.path.basename(obj.document.name) if obj.document else None

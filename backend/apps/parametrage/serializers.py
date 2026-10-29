"""UbiFleet — Paramétrage Serializers"""
from rest_framework import serializers
from .models import Parametre


class ParametreSerializer(serializers.ModelSerializer):
    valeur_typee = serializers.SerializerMethodField()
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)

    class Meta:
        model = Parametre
        fields = ['id','cle','valeur','valeur_typee','description',
                  'categorie','categorie_display','type_valeur','updated_at']
        read_only_fields = ['updated_at']

    def get_valeur_typee(self, obj):
        return obj.valeur_typee()

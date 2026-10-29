"""UbiFleet — Grand Livre Serializers"""
from rest_framework import serializers
from .models import ImportGrandLivre, LigneGrandLivre


class ImportGrandLivreSerializer(serializers.ModelSerializer):
    importe_par_nom = serializers.SerializerMethodField()

    class Meta:
        model  = ImportGrandLivre
        fields = [
            'id', 'fichier_nom', 'date_import',
            'nb_lignes', 'nb_importees', 'nb_doublons', 'nb_erreurs',
            'importe_par', 'importe_par_nom',
        ]

    def get_importe_par_nom(self, obj):
        if obj.importe_par:
            return obj.importe_par.get_full_name() or obj.importe_par.email
        return None


class LigneGrandLivreSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LigneGrandLivre
        fields = [
            'id', 'import_source',
            'code_agence', 'libelle_agence',
            'compte', 'libelle_compte',
            'date_analytique', 'date_comptable',
            'origine', 'piece', 'no_ligne', 'no_analytique',
            'libelle_ecriture', 'debit', 'credit',
            'created_at',
        ]

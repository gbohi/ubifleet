"""UbiFleet — Total Import Serializers"""

from rest_framework import serializers
from .models import TransactionCarburant, ImportTotal


class TransactionCarburantSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TransactionCarburant
        fields = '__all__'


class ImportTotalSerializer(serializers.ModelSerializer):
    importe_par_nom = serializers.SerializerMethodField()

    class Meta:
        model  = ImportTotal
        fields = [
            'id', 'fichier_nom', 'date_import',
            'nb_lignes', 'nb_importees', 'nb_doublons', 'nb_erreurs',
            'importé_par', 'importe_par_nom',
        ]

    def get_importe_par_nom(self, obj):
        if obj.importé_par:
            return obj.importé_par.get_full_name() or obj.importé_par.email
        return None

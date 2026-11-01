"""UbiFleet — Total Import Serializers"""

from rest_framework import serializers
from .models import TransactionCarburant, ImportTotal


class TransactionCarburantSerializer(serializers.ModelSerializer):
    vehicule_connu = serializers.SerializerMethodField()

    class Meta:
        model  = TransactionCarburant
        fields = '__all__'

    def get_vehicule_connu(self, obj):
        """Plaque présente dans le parc UbiFleet (comparaison normalisée)."""
        plaques = self.context.get('plaques_parc')
        if plaques is None:
            return None
        from apps.carburant.analyses import normaliser_immat
        return normaliser_immat(obj.immatriculation) in plaques


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

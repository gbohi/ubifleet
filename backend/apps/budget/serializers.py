"""UbiFleet — Budget Serializers"""

from rest_framework import serializers
from .models import BudgetAnnuel, DepenseVehicule


class BudgetAnnuelSerializer(serializers.ModelSerializer):
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)
    budget_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    realise = serializers.SerializerMethodField()

    class Meta:
        model = BudgetAnnuel
        fields = [
            'id', 'agence', 'agence_nom', 'annee',
            'budget_carburant', 'budget_entretien', 'budget_reparations',
            'budget_assurances', 'budget_pneumatiques', 'budget_divers',
            'budget_total', 'realise', 'notes'
        ]

    def get_realise(self, obj):
        from django.db.models import Sum
        depenses = DepenseVehicule.objects.filter(
            agence=obj.agence,
            date_depense__year=obj.annee
        ).values('categorie').annotate(total=Sum('montant'))
        return {dep['categorie']: float(dep['total']) for dep in depenses}


class DepenseSerializer(serializers.ModelSerializer):
    vehicule_immat = serializers.SerializerMethodField()
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)
    agence_nom = serializers.CharField(source='agence.nom', read_only=True)

    class Meta:
        model = DepenseVehicule
        fields = [
            'id', 'vehicule', 'vehicule_immat', 'agence', 'agence_nom',
            'categorie', 'categorie_display', 'date_depense', 'montant',
            'description', 'fournisseur', 'numero_facture',
            'fichier_justificatif', 'created_at', 'automatique', 'ref_objet_id'
        ]
        read_only_fields = ['created_at', 'ref_objet_id']

    automatique = serializers.SerializerMethodField()

    def get_automatique(self, obj):
        """Dépense générée par une prise de carburant : elle se modifie par la prise."""
        from apps.carburant.depenses import REF_PRISE
        return obj.ref_objet_type == REF_PRISE

    def get_vehicule_immat(self, obj):
        return obj.vehicule.immatriculation if obj.vehicule else None

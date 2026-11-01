"""UbiFleet — Budget Serializers"""

from rest_framework import serializers
from .models import BudgetAnnuel, DepenseVehicule


def realise_par_poste(lignes):
    """Réalisé par poste du budget annuel (carburant, entretien, réparations,
    assurances, pneumatiques, divers), d'après le poste de chaque catégorie de
    dépense (Paramètres › Catégories de dépense) ; catégorie inconnue → divers."""
    from apps.parametrage.models import CategorieDepense
    postes = dict(CategorieDepense.objects.values_list('code', 'poste_budget'))
    realise = {p: 0.0 for p in CategorieDepense.PosteBudget.values}
    for ligne in lignes:
        poste = postes.get(ligne['categorie'], CategorieDepense.PosteBudget.DIVERS)
        realise[poste] += float(ligne['total'] or 0)
    return realise


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
        return realise_par_poste(depenses)


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
            'fichier_justificatif', 'created_at', 'automatique', 'origine', 'ref_objet_type', 'ref_objet_id'
        ]
        read_only_fields = ['created_at', 'ref_objet_type', 'ref_objet_id']

    automatique = serializers.SerializerMethodField()

    origine = serializers.SerializerMethodField()

    def get_automatique(self, obj):
        """Dépense reportée d'un autre module : elle se modifie par sa source."""
        from .automatiques import ORIGINES
        return obj.ref_objet_type in ORIGINES

    def get_origine(self, obj):
        from .automatiques import ORIGINES
        return ORIGINES.get(obj.ref_objet_type, 'Saisie manuelle')

    def validate_categorie(self, value):
        from apps.core.referentiels import valider_code_referentiel
        from apps.parametrage.models import CategorieDepense
        return valider_code_referentiel(CategorieDepense, value,
                                        self.instance.categorie if self.instance else None,
                                        'Catégorie de dépense')

    def get_vehicule_immat(self, obj):
        return obj.vehicule.immatriculation if obj.vehicule else None

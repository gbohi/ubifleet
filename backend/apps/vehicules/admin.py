"""UbiFleet — Admin Vehicules"""

from django.contrib import admin
from .models import ReleveKilometrage, HistoriqueImmatriculation, AffectationVehicule

@admin.register(ReleveKilometrage)
class ReleveKilometrageAdmin(admin.ModelAdmin):
    list_display = ['vehicule', 'kilometrage', 'date_releve', 'type_mouvement', 'tournee']
    list_filter  = ['type_mouvement', 'date_releve']
    search_fields = ['vehicule__immatriculation', 'tournee']

@admin.register(HistoriqueImmatriculation)
class HistoriqueImmatriculationAdmin(admin.ModelAdmin):
    list_display = ['vehicule', 'ancienne_immatriculation', 'nouvelle_immatriculation',
                    'date_changement', 'motif']
    list_filter  = ['date_changement']
    search_fields = ['ancienne_immatriculation', 'nouvelle_immatriculation']
from .models import Vehicule, DocumentVehicule


admin.site.register(Vehicule)
admin.site.register(DocumentVehicule)

@admin.register(AffectationVehicule)
class AffectationVehiculeAdmin(admin.ModelAdmin):
    list_display  = ['vehicule', 'chauffeur', 'date_debut', 'date_fin', 'est_active']
    list_filter   = ['date_debut']
    search_fields = ['vehicule__immatriculation', 'chauffeur__nom', 'chauffeur__prenom']

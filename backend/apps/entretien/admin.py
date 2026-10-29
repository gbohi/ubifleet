"""UbiFleet — Admin Entretien"""

from django.contrib import admin
from .models import TypeIntervention, Prestataire, Intervention, SuiviPneus


admin.site.register(TypeIntervention)
admin.site.register(Prestataire)
admin.site.register(Intervention)
admin.site.register(SuiviPneus)

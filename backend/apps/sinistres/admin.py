"""UbiFleet — Admin Sinistres"""

from django.contrib import admin
from .models import Assureur, ContratAssurance, Sinistre, PieceJointeSinistre


admin.site.register(Assureur)
admin.site.register(ContratAssurance)
admin.site.register(Sinistre)
admin.site.register(PieceJointeSinistre)

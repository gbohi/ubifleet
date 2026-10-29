"""UbiFleet — Admin Carburant"""

from django.contrib import admin
from .models import Station, DotationCarburant, PleinsCarburant, RapprochementCarburant


admin.site.register(Station)
admin.site.register(DotationCarburant)
admin.site.register(PleinsCarburant)
admin.site.register(RapprochementCarburant)

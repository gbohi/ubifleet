"""UbiFleet — Admin Budget"""

from django.contrib import admin
from .models import BudgetAnnuel, DepenseVehicule


admin.site.register(BudgetAnnuel)
admin.site.register(DepenseVehicule)

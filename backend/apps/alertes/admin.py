"""UbiFleet — Admin Alertes"""

from django.contrib import admin
from .models import Alerte


admin.site.register(Alerte)

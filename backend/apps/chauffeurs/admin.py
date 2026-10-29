"""UbiFleet — Admin Chauffeurs"""

from django.contrib import admin
from .models import Chauffeur


admin.site.register(Chauffeur)

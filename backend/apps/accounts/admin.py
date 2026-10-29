"""UbiFleet — Admin Accounts"""

from django.contrib import admin
from .models import User, Agence, PermissionRole

@admin.register(PermissionRole)
class PermissionRoleAdmin(admin.ModelAdmin):
    list_display  = ['role', 'module', 'action', 'autorise']
    list_filter   = ['role', 'module', 'autorise']
    list_editable = ['autorise']
    ordering      = ['role', 'module', 'action']
from .models import Agence, User


admin.site.register(Agence)
admin.site.register(User)

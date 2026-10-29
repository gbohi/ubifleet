"""UbiFleet — URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

API = 'api/v1/'

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path(API + 'auth/', include('apps.accounts.urls')),

    # Modules métier
    path(API + 'vehicules/', include('apps.vehicules.urls')),
    path(API + 'carburant/', include('apps.carburant.urls')),
    path(API + 'entretien/', include('apps.entretien.urls')),
    path(API + 'sinistres/', include('apps.sinistres.urls')),
    path(API + 'budget/', include('apps.budget.urls')),
    path(API + 'chauffeurs/', include('apps.chauffeurs.urls')),
    path(API + 'alertes/', include('apps.alertes.urls')),
    path(API + 'rapports/', include('apps.rapports.urls')),
    path(API + 'parametrage/', include('apps.parametrage.urls')),
    path(API + 'total-import/', include('apps.total_import.urls')),
    path(API + 'grand-livre/', include('apps.grand_livre.urls')),
    path(API + 'controle/', include('apps.controle.urls')),
    path(API + 'demandes/', include('apps.demandes.urls')),

    # OpenAPI / Swagger
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

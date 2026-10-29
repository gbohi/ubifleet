from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SinistreViewSet, ContratAssuranceViewSet, AssureurViewSet

router = DefaultRouter()
router.register('sinistres', SinistreViewSet, basename='sinistre')
router.register('contrats', ContratAssuranceViewSet, basename='contrat-assurance')
router.register('assureurs', AssureurViewSet, basename='assureur')

urlpatterns = [path('', include(router.urls))]

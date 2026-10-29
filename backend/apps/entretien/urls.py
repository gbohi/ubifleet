from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InterventionViewSet, TypeInterventionViewSet,
    PrestataireViewSet, PneusViewSet,
    DocumentInterventionViewSet,
)

router = DefaultRouter()
router.register('interventions', InterventionViewSet, basename='intervention')
router.register('types',         TypeInterventionViewSet, basename='type-intervention')
router.register('prestataires',  PrestataireViewSet, basename='prestataire')
router.register('pneus',         PneusViewSet, basename='pneu')
router.register('documents',     DocumentInterventionViewSet, basename='document-intervention')

urlpatterns = [path('', include(router.urls))]

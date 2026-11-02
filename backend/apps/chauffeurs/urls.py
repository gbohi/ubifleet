"""UbiFleet — Chauffeurs URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ChauffeurViewSet, DocumentChauffeurViewSet

router = DefaultRouter()
# « documents » avant le CRUD des chauffeurs (sinon pris pour un identifiant)
router.register('documents', DocumentChauffeurViewSet, basename='document-chauffeur')
router.register('', ChauffeurViewSet, basename='chauffeur')
urlpatterns = [path('', include(router.urls))]

"""UbiFleet — Chauffeurs URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ChauffeurViewSet

router = DefaultRouter()
router.register('', ChauffeurViewSet, basename='chauffeur')
urlpatterns = [path('', include(router.urls))]

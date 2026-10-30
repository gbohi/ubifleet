"""UbiFleet — Carburant URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('pleins', views.PleinViewSet, basename='plein')
router.register('dotations', views.DotationViewSet, basename='dotation')
router.register('stations', views.StationViewSet, basename='station')
router.register('rapprochements', views.RapprochementViewSet, basename='rapprochement')
router.register('prix', views.PrixCarburantViewSet, basename='prix-carburant')

urlpatterns = [path('', include(router.urls))]

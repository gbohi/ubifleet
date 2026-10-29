"""UbiFleet — Grand Livre URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('imports', views.ImportGrandLivreViewSet, basename='gl-import')
router.register('lignes',  views.LigneGrandLivreViewSet,  basename='gl-ligne')

urlpatterns = [path('', include(router.urls))]

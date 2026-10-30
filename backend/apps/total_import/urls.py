"""UbiFleet — Total Import URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('historique',    views.ImportTotalViewSet,          basename='import-total')
router.register('transactions',    views.TransactionCarburantViewSet, basename='transaction-carburant')

urlpatterns = [
    path('', include(router.urls)),
]

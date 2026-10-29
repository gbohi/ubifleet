"""UbiFleet — Budget URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BudgetViewSet, DepenseViewSet

router = DefaultRouter()
router.register('budgets', BudgetViewSet, basename='budget')
router.register('depenses', DepenseViewSet, basename='depense')

urlpatterns = [path('', include(router.urls))]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AlerteViewSet

router = DefaultRouter()
router.register('', AlerteViewSet, basename='alerte')
urlpatterns = [path('', include(router.urls))]

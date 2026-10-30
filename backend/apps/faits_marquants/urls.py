from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FaitMarquantViewSet

router = DefaultRouter()
router.register('', FaitMarquantViewSet, basename='fait-marquant')
urlpatterns = [path('', include(router.urls))]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SinistreViewSet, ContratAssuranceViewSet, AssureurViewSet, PieceJointeSinistreViewSet

router = DefaultRouter()
router.register('sinistres', SinistreViewSet, basename='sinistre')
router.register('contrats', ContratAssuranceViewSet, basename='contrat-assurance')
router.register('assureurs', AssureurViewSet, basename='assureur')
router.register('pieces-jointes', PieceJointeSinistreViewSet, basename='piece-jointe-sinistre')

urlpatterns = [path('', include(router.urls))]

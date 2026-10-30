from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ParametreViewSet, TourneeViewSet,
    AffectationUsageViewSet, StatutVehiculeViewSet,
    MarqueVehiculeViewSet, ModeleVehiculeViewSet, TypeMouvementViewSet,
)

router = DefaultRouter()
router.register('tournees',    TourneeViewSet,           basename='tournee')
router.register('affectations',AffectationUsageViewSet,  basename='affectation-usage')
router.register('statuts',     StatutVehiculeViewSet,     basename='statut-vehicule')
router.register('marques',     MarqueVehiculeViewSet,     basename='marque-vehicule')
router.register('modeles',     ModeleVehiculeViewSet,     basename='modele-vehicule')
router.register('types-mouvement', TypeMouvementViewSet,  basename='type-mouvement')

urlpatterns = [
    path('',              ParametreViewSet.as_view({'get': 'list'}),         name='parametre-list'),
    path('by_categorie/', ParametreViewSet.as_view({'get': 'by_categorie'}), name='parametre-by-cat'),
    path('bulk_update/',  ParametreViewSet.as_view({'post': 'bulk_update'}), name='parametre-bulk'),
    path('<int:pk>/',     ParametreViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}),
         name='parametre-detail'),
    path('', include(router.urls)),
]

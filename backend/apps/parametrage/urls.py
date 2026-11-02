from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ParametreViewSet, TourneeViewSet, FenetreSaisieView, CorrectionSaisieViewSet,
    AffectationUsageViewSet, StatutVehiculeViewSet,
    MarqueVehiculeViewSet, ModeleVehiculeViewSet, TypeMouvementViewSet, TypeVehiculeViewSet,
    CategorieDepenseViewSet, TypeSinistreViewSet, TypeContratAssuranceViewSet, TypeDocumentChauffeurViewSet,
)

router = DefaultRouter()
router.register('tournees',    TourneeViewSet,           basename='tournee')
router.register('affectations',AffectationUsageViewSet,  basename='affectation-usage')
router.register('statuts',     StatutVehiculeViewSet,     basename='statut-vehicule')
router.register('marques',     MarqueVehiculeViewSet,     basename='marque-vehicule')
router.register('modeles',     ModeleVehiculeViewSet,     basename='modele-vehicule')
router.register('types-mouvement', TypeMouvementViewSet,  basename='type-mouvement')
router.register('types-vehicule', TypeVehiculeViewSet,    basename='type-vehicule')
router.register('categories-depense', CategorieDepenseViewSet, basename='categorie-depense')
router.register('types-sinistre', TypeSinistreViewSet,    basename='type-sinistre')
router.register('types-contrat', TypeContratAssuranceViewSet, basename='type-contrat')
router.register('types-document-chauffeur', TypeDocumentChauffeurViewSet, basename='type-document-chauffeur')
router.register('corrections', CorrectionSaisieViewSet,  basename='correction-saisie')

urlpatterns = [
    path('',              ParametreViewSet.as_view({'get': 'list'}),         name='parametre-list'),
    path('by_categorie/', ParametreViewSet.as_view({'get': 'by_categorie'}), name='parametre-by-cat'),
    path('fenetre-saisie/', FenetreSaisieView.as_view({'get': 'list'}), name='fenetre-saisie'),
    path('bulk_update/',  ParametreViewSet.as_view({'post': 'bulk_update'}), name='parametre-bulk'),
    path('<int:pk>/',     ParametreViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}),
         name='parametre-detail'),
    path('', include(router.urls)),
]

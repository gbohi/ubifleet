"""UbiFleet — Demandes URLs — toutes les routes sont explicites"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    TypeDemandeViewSet, DemandeViewSet,
    NiveauValidationViewSet, LigneDemandeAchatViewSet,
)

# Routers séparés pour chaque ViewSet auxiliaire
types_router   = DefaultRouter()
niveaux_router = DefaultRouter()
lignes_router  = DefaultRouter()

types_router.register('',   TypeDemandeViewSet,       basename='type-demande')
niveaux_router.register('', NiveauValidationViewSet,   basename='niveau-validation')
lignes_router.register('',  LigneDemandeAchatViewSet, basename='ligne-achat')

urlpatterns = [
    # ══ DEMANDES — toutes les routes explicites ══════════════════════
    path('',
         DemandeViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='demande-list'),
    path('stats/',
         DemandeViewSet.as_view({'get': 'stats'}),
         name='demande-stats'),
    path('a_valider/',
         DemandeViewSet.as_view({'get': 'a_valider'}),
         name='demande-a-valider'),
    path('<uuid:pk>/',
         DemandeViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='demande-detail'),
    path('<uuid:pk>/valider/',
         DemandeViewSet.as_view({'post': 'valider'}),
         name='demande-valider'),
    path('<uuid:pk>/rejeter/',
         DemandeViewSet.as_view({'post': 'rejeter'}),
         name='demande-rejeter'),
    path('<uuid:pk>/soumettre/',
         DemandeViewSet.as_view({'post': 'soumettre'}),
         name='demande-soumettre'),
    path('<uuid:pk>/annuler/',
         DemandeViewSet.as_view({'post': 'annuler'}),
         name='demande-annuler'),

    # ══ LIGNES ACHAT ════════════════════════════════════════════════
    path('lignes/bulk_save/',
         LigneDemandeAchatViewSet.as_view({'post': 'bulk_save'}),
         name='lignes-bulk-save'),
    path('lignes/',
         LigneDemandeAchatViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='ligne-list'),
    path('lignes/<int:pk>/',
         LigneDemandeAchatViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='ligne-detail'),

    # ══ TYPES DE DEMANDE ════════════════════════════════════════════
    path('types/',
         TypeDemandeViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='type-demande-list'),
    path('types/<int:pk>/',
         TypeDemandeViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='type-demande-detail'),

    # ══ NIVEAUX DE VALIDATION ════════════════════════════════════════
    path('niveaux/',
         NiveauValidationViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='niveau-list'),
    path('niveaux/<int:pk>/',
         NiveauValidationViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='niveau-detail'),
]

"""UbiFleet — Contrôle Véhicule URLs — toutes routes explicites"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ElementControleViewSet, FicheControleViewSet,
    PointControleDetailViewSet, PhotoControleViewSet,
)

router = DefaultRouter()
router.register('elements', ElementControleViewSet, basename='element-controle')

urlpatterns = [
    # ══ FICHES — routes explicites avec UUID ════════════════════════
    path('fiches/',
         FicheControleViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='fiche-list'),
    path('fiches/stats/',
         FicheControleViewSet.as_view({'get': 'stats'}),
         name='fiche-stats'),
    path('fiches/<uuid:pk>/',
         FicheControleViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='fiche-detail'),
    path('fiches/<uuid:pk>/valider/',
         FicheControleViewSet.as_view({'post': 'valider'}),
         name='fiche-valider'),
    path('fiches/<uuid:pk>/rapport/',
         FicheControleViewSet.as_view({'get': 'rapport'}),
         name='fiche-rapport'),

    # ══ POINTS — bulk_save AVANT les routes génériques ══════════════
    path('points/bulk_save/',
         PointControleDetailViewSet.as_view({'post': 'bulk_save'}),
         name='points-bulk-save'),
    path('points/',
         PointControleDetailViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='points-list'),
    path('points/<int:pk>/',
         PointControleDetailViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='points-detail'),

    # ══ PHOTOS ══════════════════════════════════════════════════════
    path('photos/',
         PhotoControleViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='photo-list'),
    path('photos/<int:pk>/',
         PhotoControleViewSet.as_view({
             'get': 'retrieve', 'delete': 'destroy',
         }), name='photo-detail'),

    # ══ ÉLÉMENTS (via router — pas de conflits) ══════════════════════
    path('', include(router.urls)),
]

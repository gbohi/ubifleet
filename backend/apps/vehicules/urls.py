"""UbiFleet — Vehicules URLs — toutes les routes explicites"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VehiculeViewSet, DocumentVehiculeViewSet,
    ReleveKilometrageViewSet, HistoriqueImmatriculationViewSet,
    HistoriqueStatutVehiculeViewSet,
    AffectationVehiculeViewSet, TypeDocumentVehiculeViewSet,
    ConsommationKmView, UtilisationParcView,
)

urlpatterns = [
    # ── Routes fixes (avant tout) ────────────────────────────────────
    path('releves-km/', include([
        path('', ReleveKilometrageViewSet.as_view({'get': 'list', 'post': 'create'})),
        path('<uuid:pk>/', ReleveKilometrageViewSet.as_view({
            'get': 'retrieve', 'put': 'update',
            'patch': 'partial_update', 'delete': 'destroy',
        })),
    ])),
    path('historique-immat/', include([
        path('', HistoriqueImmatriculationViewSet.as_view({'get': 'list'})),
        path('<uuid:pk>/', HistoriqueImmatriculationViewSet.as_view({'get': 'retrieve'})),
    ])),
    path('affectations/', include([
        path('', AffectationVehiculeViewSet.as_view({'get': 'list', 'post': 'create'})),
        path('<uuid:pk>/', AffectationVehiculeViewSet.as_view({
            'get': 'retrieve', 'put': 'update',
            'patch': 'partial_update', 'delete': 'destroy',
        })),
    ])),
    path('consommation-km/', ConsommationKmView.as_view({'get': 'list'}),
         name='consommation-km'),
    path('utilisation/', UtilisationParcView.as_view({'get': 'list'}), name='utilisation-parc'),
    path('utilisation/courbe/', UtilisationParcView.as_view({'get': 'courbe'}), name='utilisation-parc-courbe'),
    path('types-document/', TypeDocumentVehiculeViewSet.as_view({
        'get': 'list', 'post': 'create',
    }), name='types-document-list'),
    path('types-document/<int:pk>/', TypeDocumentVehiculeViewSet.as_view({
        'get': 'retrieve', 'put': 'update',
        'patch': 'partial_update', 'delete': 'destroy',
    }), name='types-document-detail'),

    # ── Véhicules CRUD ────────────────────────────────────────────────
    path('', VehiculeViewSet.as_view({
        'get': 'list', 'post': 'create',
    }), name='vehicule-list'),
    path('etat_parc/', VehiculeViewSet.as_view({'get': 'etat_parc'}),
         name='vehicule-etat-parc'),
    path('stats/', VehiculeViewSet.as_view({'get': 'stats'}),
         name='vehicule-stats'),

    # ── Véhicule par UUID ────────────────────────────────────────────
    path('<uuid:pk>/', VehiculeViewSet.as_view({
        'get': 'retrieve', 'put': 'update',
        'patch': 'partial_update', 'delete': 'destroy',
    }), name='vehicule-detail'),
    path('<uuid:pk>/kilometrage/', VehiculeViewSet.as_view({'post': 'kilometrage'}),
         name='vehicule-kilometrage'),
    path('<uuid:pk>/changer_immatriculation/', VehiculeViewSet.as_view({'post': 'changer_immatriculation'}),
         name='vehicule-changer-immat'),


    # ── Routes imbriquées par véhicule ───────────────────────────────
    path('<uuid:vehicule_pk>/documents/', include([
        path('', DocumentVehiculeViewSet.as_view({'get': 'list', 'post': 'create'}),
             name='vehicule-documents-list'),
        path('<uuid:pk>/', DocumentVehiculeViewSet.as_view({
            'get': 'retrieve', 'put': 'update',
            'patch': 'partial_update', 'delete': 'destroy',
        }), name='vehicule-documents-detail'),
    ])),
    path('<uuid:vehicule_pk>/historique-statuts/', include([
        path('', HistoriqueStatutVehiculeViewSet.as_view({'get': 'list', 'post': 'create'})),
        path('<uuid:pk>/', HistoriqueStatutVehiculeViewSet.as_view({'get': 'retrieve'})),
    ])),
]

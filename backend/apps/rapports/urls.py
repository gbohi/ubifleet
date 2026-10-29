from django.urls import path
from .views import (
    RapportEffectifParcView,
    DashboardDGView,
    RapportCarburantView,
    RapportCoutsView,
    RapportMultiAgencesView,
    RapportSinistresView,
    RapportInterventionsView,
    RapportPneusView,
)

urlpatterns = [
    path('dashboard/',     DashboardDGView.as_view(),        name='dashboard-dg'),
    path('carburant/',     RapportCarburantView.as_view(),   name='rapport-carburant'),
    path('couts/',         RapportCoutsView.as_view(),       name='rapport-couts'),
    path('multi-agences/', RapportMultiAgencesView.as_view(),name='rapport-multi-agences'),
    path('sinistres/',     RapportSinistresView.as_view(),   name='rapport-sinistres'),
    path('interventions/', RapportInterventionsView.as_view(),name='rapport-interventions'),
    path('pneus/',         RapportPneusView.as_view(),       name='rapport-pneus'),
    path('effectif-parc/',  RapportEffectifParcView.as_view(), name='rapport-effectif-parc'),
]

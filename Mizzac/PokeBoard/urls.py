from django.urls import path

from .views import (
    CatalogueView,
    CollectionOperationCreateView,
    CollectibleValuationCreateView,
    CollectionView,
    OperationsView,
    OwnedLotCreateView,
    PokeBoardDashboardView,
    PositionsRedirectView,
    ReportView,
    StaleValuationUpdateView,
    ValuationsView,
)


app_name = "pokeboard"


urlpatterns = [
    path("", CollectionView.as_view(), name="collection"),
    path("dashboard/", PokeBoardDashboardView.as_view(), name="dashboard"),
    path("catalogue/", CatalogueView.as_view(), name="catalogue"),
    path("positions/", PositionsRedirectView.as_view(), name="positions"),
    path("operations/", OperationsView.as_view(), name="operations"),
    path("operations/add/", CollectionOperationCreateView.as_view(), name="add_operation"),
    path("collection/add/", OwnedLotCreateView.as_view(), name="add_lot"),
    path("report/", ReportView.as_view(), name="report"),
    path("valuations/", ValuationsView.as_view(), name="valuations"),
    path("valuations/add/", CollectibleValuationCreateView.as_view(), name="add_valuation"),
    path("valuations/update/", StaleValuationUpdateView.as_view(), name="stale_valuations"),
]

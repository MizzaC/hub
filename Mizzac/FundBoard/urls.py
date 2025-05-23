from django.urls import path
from .views import (
    FundBoardView, PortfolioView, TransactionsView,
    SubscriptionsView, AddSubscriptionView, EditSubscriptionView, DeleteSubscriptionView,
    RevenuesView, AccountsView,
    AccountSourceModal, AddAccountModal, EditAccountModal, DeleteAccountModal
)

app_name = "fundboard"

urlpatterns = [
    path("", FundBoardView.as_view(), name="fundboard"),
    path("portfolio/",     PortfolioView.as_view(),     name="portfolio"),
    path("transactions/",  TransactionsView.as_view(),  name="transactions"),

    # Abonnements
    path("subscriptions/",                   SubscriptionsView.as_view(),      name="subscriptions"),
    path("subscriptions/add/",               AddSubscriptionView.as_view(),    name="add_subscription"),
    path("subscriptions/edit/<int:pk>/",     EditSubscriptionView.as_view(),   name="edit_subscription"),
    path("subscriptions/delete/<int:pk>/",   DeleteSubscriptionView.as_view(), name="delete_subscription"),

    # Revenus
    path("revenues/", RevenuesView.as_view(), name="revenues"),

    # Comptes
    path("accounts/", AccountsView.as_view(), name="accounts"),
    path("accounts/add/select/",             AccountSourceModal.as_view(),  name="account_source_modal"),
    path("accounts/add/modal/",              AddAccountModal.as_view(),     name="add_account_modal"),
    path("accounts/<int:pk>/edit/modal/",    EditAccountModal.as_view(),    name="edit_account_modal"),
    path("accounts/<int:pk>/delete/modal/",  DeleteAccountModal.as_view(),  name="delete_account_modal"),
]

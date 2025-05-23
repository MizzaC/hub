from django.urls import path
from .views import (
    FundBoardView, PortfolioView, TransactionsView,
    SubscriptionsView, AddSubscriptionModal, EditSubscriptionModal, DeleteSubscriptionModal,
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
    path("subscriptions/add/modal/",   AddSubscriptionModal.as_view(),  name="add_subscription_modal"),
    path("subscriptions/<int:pk>/edit/modal/", EditSubscriptionModal.as_view(), name="edit_subscription_modal"),
    path("subscriptions/<int:pk>/delete/modal/",   DeleteSubscriptionModal.as_view(), name="delete_subscription_modal"),

    # Revenus
    path("revenues/", RevenuesView.as_view(), name="revenues"),

    # Comptes
    path("accounts/", AccountsView.as_view(), name="accounts"),
    path("accounts/add/select/",             AccountSourceModal.as_view(),  name="account_source_modal"),
    path("accounts/add/modal/",              AddAccountModal.as_view(),     name="add_account_modal"),
    path("accounts/<int:pk>/edit/modal/",    EditAccountModal.as_view(),    name="edit_account_modal"),
    path("accounts/<int:pk>/delete/modal/",  DeleteAccountModal.as_view(),  name="delete_account_modal"),
]

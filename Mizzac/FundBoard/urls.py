# FundBoard/urls.py

from django.urls import path
from .views import (
    FundBoardView,
    PortfolioView,
    TransactionsView,
    SubscriptionsView,
    AddSubscriptionView,
    EditSubscriptionView,
    DeleteSubscriptionView,
    RevenuesView,
    AccountsView,
)
from .views import (
    AddAccountModal, EditAccountModal, DeleteAccountModal, AccountSourceModal
)
from django.contrib.auth import views as auth_views

app_name = 'fundboard'

urlpatterns = [
    path("", FundBoardView.as_view(), name="fundboard"),
    path("portfolio/",     PortfolioView.as_view(),     name="portfolio"),
    path("transactions/",  TransactionsView.as_view(),  name="transactions"),
    path("subscriptions/", SubscriptionsView.as_view(), name="subscriptions"),
    # tant que pas de modal
    path('subscriptions/add/', AddSubscriptionView.as_view(), name='add_subscription'),
    path('subscriptions/edit/<int:pk>/', EditSubscriptionView.as_view(), name='edit_subscription'),
    path('subscriptions/delete/<int:pk>/', DeleteSubscriptionView.as_view(), name='delete_subscription'),
    path("revenues/",      RevenuesView.as_view(),      name="revenues"),

    path("accounts/", AccountsView.as_view(), name="accounts"),

    # ---- Modales AJAX ----
    path("accounts/add/modal/",                AddAccountModal.as_view(),   name="add_account_modal"),
    path("accounts/<int:pk>/edit/modal/",      EditAccountModal.as_view(),  name="edit_account_modal"),
    path("accounts/<int:pk>/delete/modal/",    DeleteAccountModal.as_view(),name="delete_account_modal"),
    path("accounts/add/select/",               AccountSourceModal.as_view(),  name="account_source_modal"),
    path("accounts/add/modal/",                AddAccountModal.as_view(),     name="add_account_modal"),
]

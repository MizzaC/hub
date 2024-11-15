# FundBoard/urls.py

from django.urls import path
from .views import (
    FundBoardView,
    PortfolioView,
    TransactionsView,
    SubscriptionsView,
    RevenuesView,
    AccountsView,
    AddAccountView,
    EditAccountView,
    DeleteAccountView,
    AddSubscriptionView
)
from django.contrib.auth import views as auth_views

app_name = 'fundboard'

urlpatterns = [
    # FundBoard Homepage (Tableau de Bord)
    path('', FundBoardView.as_view(), name='fundboard'),

    # Portefeuille
    path('portfolio/', PortfolioView.as_view(), name='portfolio'),

    # Transactions
    path('transactions/', TransactionsView.as_view(), name='transactions'),

    # Abonnements
    path('subscriptions/', SubscriptionsView.as_view(), name='subscriptions'),
    path('subscriptions/add/', AddSubscriptionView.as_view(), name='add_subscription'),

    # Revenus
    path('revenues/', RevenuesView.as_view(), name='revenues'),

    # Comptes Bancaires
    path('accounts/', AccountsView.as_view(), name='accounts'),
    path('accounts/add/', AddAccountView.as_view(), name='add_account'),
    path('accounts/edit/<int:pk>/', EditAccountView.as_view(), name='edit_account'),
    path('accounts/delete/<int:pk>/', DeleteAccountView.as_view(), name='delete_account'),

    # Authentification
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', auth_views.LoginView.as_view(template_name='registration/signup.html'), name='signup'),
]

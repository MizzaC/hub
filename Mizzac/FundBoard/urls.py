# FundBoard/urls.py
from django.urls import path

from .views import (
    # main pages
    FundBoardView, PortfolioView, TransactionsView,
    ExpensesView, RevenuesView, SubscriptionsRedirectView,

    # account modals
    AccountSourceModal, AddAccountModal, EditAccountModal, DeleteAccountModal,

    # unified expense modals
    AddExpenseModal, EditExpenseModal, DeleteExpenseModal,

    # lists
    AccountsView,
)

app_name = 'fundboard'

urlpatterns = [
    # Home / dashboard
    path('', FundBoardView.as_view(), name='fundboard'),

    # Portfolio & transactions
    path('portfolio/',    PortfolioView.as_view(),    name='portfolio'),
    path('transactions/', TransactionsView.as_view(), name='transactions'),

    # Unified expenses page (+ legacy redirect)
    path('expenses/',      ExpensesView.as_view(),            name='expenses'),
    path('subscriptions/', SubscriptionsRedirectView.as_view(), name='subscriptions'),

    # Revenues
    path('revenues/', RevenuesView.as_view(), name='revenues'),

    # Accounts list
    path('accounts/', AccountsView.as_view(), name='accounts'),

    # ----- Account modals (AJAX fragments) -----
    path('accounts/add/select/',            AccountSourceModal.as_view(),  name='account_source_modal'),
    path('accounts/add/modal/',             AddAccountModal.as_view(),     name='add_account_modal'),
    path('accounts/<int:pk>/edit/modal/',   EditAccountModal.as_view(),    name='edit_account_modal'),
    path('accounts/<int:pk>/delete/modal/', DeleteAccountModal.as_view(),  name='delete_account_modal'),

    # ----- Unified Expense modals (recurring OR one-time) -----
    path('expenses/add/modal/',             AddExpenseModal.as_view(),     name='add_expense_modal'),
    path('expenses/<int:pk>/edit/modal/',   EditExpenseModal.as_view(),    name='edit_expense_modal'),
    path('expenses/<int:pk>/delete/modal/', DeleteExpenseModal.as_view(),  name='delete_expense_modal'),
]

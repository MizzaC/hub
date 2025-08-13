# FundBoard/urls.py
from django.urls import path
from .views import (
    # pages
    FundBoardView,
    PortfolioView,
    TransactionsView,
    ExpensesView,
    AssetsView,
    AccountsView,
    RevenuesView,
    SubscriptionsRedirectView,
    # account modals
    AccountSourceModal,
    AddAccountModal,
    EditAccountModal,
    DeleteAccountModal,
    # expense modals
    AddExpenseModal,
    EditExpenseModal,
    DeleteExpenseModal,
)

app_name = 'fundboard'

urlpatterns = [
    path("", FundBoardView.as_view(), name="fundboard"),
    path("portfolio/",     PortfolioView.as_view(),     name="portfolio"),
    path("transactions/",  TransactionsView.as_view(),  name="transactions"),
    path("expenses/",      ExpensesView.as_view(),      name="expenses"),
    path("assets/",        AssetsView.as_view(),        name="assets"),
    path("accounts/",      AccountsView.as_view(),      name="accounts"),
    path("revenues/",      RevenuesView.as_view(),      name="revenues"),

    # Legacy redirect from /subscriptions/ -> /expenses/
    path("subscriptions/", SubscriptionsRedirectView.as_view(), name="subscriptions"),

    # ---- Account modals ----
    path("accounts/add/select/",            AccountSourceModal.as_view(),  name="account_source_modal"),
    path("accounts/add/modal/",             AddAccountModal.as_view(),     name="add_account_modal"),
    path("accounts/<int:pk>/edit/modal/",   EditAccountModal.as_view(),    name="edit_account_modal"),
    path("accounts/<int:pk>/delete/modal/", DeleteAccountModal.as_view(),  name="delete_account_modal"),

    # ---- Expense modals ----
    path("expenses/add/modal/",             AddExpenseModal.as_view(),     name="add_expense_modal"),
    path("expenses/<int:pk>/edit/modal/",   EditExpenseModal.as_view(),    name="edit_expense_modal"),
    path("expenses/<int:pk>/delete/modal/", DeleteExpenseModal.as_view(),  name="delete_expense_modal"),
]

from __future__ import annotations

from django.contrib import admin
from .models import Account, Expense, Transaction, Income


# ---------- Account ----------

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    Admin for financial accounts (bank, CTO, PEA, crypto, ...).
    """
    list_display = (
        "name",
        "user",
        "category",      # CURRENT / SAVINGS / CTO / PEA / CRYPTO / OTHER
        "balance",
    )
    list_filter = (
        "category",
    )
    search_fields = (
        "name",
        "user__username",
    )
    ordering = ("name",)
    autocomplete_fields = ()
    readonly_fields = ()
    fieldsets = (
        (None, {
            "fields": ("user", "name", "category", "balance")
        }),
    )


# ---------- Expense ----------

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    Admin for unified expenses (one-time & recurring).
    """
    list_display = (
    "name", "user", "amount", "is_recurring", "freq",
    "start_date", "end_date", "next_due", "tag", "account",
    )
    list_filter = (
        "is_recurring",
        "freq",
        "tag",
        "account__category",
    )
    search_fields = (
        "name",
        "user__username",
        "tag",
        "account__name",
    )
    ordering = ("-next_due",)
    autocomplete_fields = ("account",)
    fieldsets = (
    ("Général", {"fields": ("user", "name", "amount", "tag", "account")}),
    ("Période", {"fields": ("start_date", "end_date", "next_due")}),
    ("Récurrence", {"fields": ("is_recurring", "freq", "freq_custom")}),
    )


# ---------- Transaction ----------

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Admin for transactions (deposits, withdrawals, buys/sells, transfers).
    """
    list_display = (
        "user",
        "account",
        "trx_type",      # DEPOSIT / WITHDRAWAL / BUY / SELL / TRANSFER
        "amount",
        "date_trx",
    )
    list_filter = (
        "trx_type",
        "account__category",
        "date_trx",
    )
    search_fields = (
        "user__username",
        "account__name",
    )
    ordering = ("-date_trx",)
    autocomplete_fields = ("account",)
    fieldsets = (
        (None, {
            "fields": ("user", "account", "trx_type", "amount", "date_trx")
        }),
    )

# ---------- Income ----------

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = (
        "name", "user", "amount", "is_recurring",
        "freq", "start_date", "end_date", "next_payday"
    )
    list_filter = ("is_recurring", "freq")
    search_fields = ("name", "user__username")
    ordering = ("-next_payday",)
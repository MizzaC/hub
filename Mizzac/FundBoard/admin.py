from __future__ import annotations

from django.contrib import admin
from .models import Account, Expense, Transaction


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
        "name",
        "user",
        "amount",
        "is_recurring",
        "freq",          # DAILY / WEEKLY / MONTHLY / YEARLY / PERSONALIZED / None
        "next_due",
        "tag",
        "account",
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
        ("General", {
            "fields": ("user", "name", "amount", "tag", "account")
        }),
        ("Recurrence", {
            "fields": ("is_recurring", "freq", "freq_custom", "next_due"),
            "description": "If not recurring, only 'next_due' is used as the expense date.",
        }),
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

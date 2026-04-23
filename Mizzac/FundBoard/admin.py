from django.contrib import admin

from .models import Account, Asset, CashflowRule, Holding, Leg, PriceHistory, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "category", "base_currency", "updated_at")
    list_filter = ("category", "base_currency")
    search_fields = ("name", "user__username")
    ordering = ("name",)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("ticker", "name", "asset_type", "precision", "sector")
    list_filter = ("asset_type",)
    search_fields = ("ticker", "name")


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("asset", "date", "close", "reference_currency")
    list_filter = ("asset", "reference_currency")
    search_fields = ("asset__ticker",)
    ordering = ("-date",)


class LegInline(admin.TabularInline):
    model = Leg
    extra = 0
    autocomplete_fields = ("account", "asset")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "trx_type",
        "executed_at",
        "is_balanced",
        "integrity_delta",
        "tolerance_applied",
    )
    list_filter = ("trx_type", "is_balanced", "executed_at")
    search_fields = ("user__username", "description", "external_reference")
    ordering = ("-executed_at",)
    inlines = [LegInline]


@admin.register(Leg)
class LegAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transaction",
        "account",
        "asset",
        "quantity",
        "value_reference",
        "reference_currency",
        "is_fee",
        "is_adjustment",
    )
    list_filter = ("reference_currency", "is_fee", "is_adjustment", "adjustment_type")
    search_fields = ("transaction__id", "account__name", "asset__ticker")
    autocomplete_fields = ("transaction", "account", "asset")


@admin.register(CashflowRule)
class CashflowRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "user",
        "amount",
        "is_recurring",
        "freq",
        "next_due",
        "default_account",
    )
    list_filter = ("kind", "is_recurring", "freq")
    search_fields = ("name", "user__username", "tag")
    ordering = ("next_due",)
    autocomplete_fields = ("default_account",)


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ("user", "account", "asset", "quantity", "avg_cost_reference", "reference_currency")
    list_filter = ("reference_currency",)
    search_fields = ("user__username", "account__name", "asset__ticker")

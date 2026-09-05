from django.contrib import admin

from .models import (
    Account,
    CompoundInterestScenario,
    Connection,
    ConnectorSyncRun,
    ExchangeRate,
    ExternalIdentifier,
    FinancialAuditEvent,
    ImportBatch,
    ImportChange,
    ImportIssue,
    Income,
    Institution,
    Instrument,
    Loan,
    LoanBalanceSnapshot,
    LoanSimulationScenario,
    MaintenanceRun,
    MarketDataPreference,
    MarketDataStatus,
    Notification,
    Position,
    Price,
    PrivateEquityHolding,
    PrivateEquityValuation,
    RealEstate,
    RealEstateValuation,
    Snapshot,
    Subscription,
    Transaction,
    VirtualCashEvent,
    VirtualCorporateAction,
    VirtualOrder,
    VirtualPortfolio,
    VirtualPortfolioSnapshot,
    VirtualPosition,
    VirtualWatchlistEntry,
    WatchInstrument,
    Watchlist,
)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name", "institution_type", "country_code", "status")
    list_filter = ("institution_type", "status", "country_code")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "provider", "institution", "status", "last_synced_at")
    list_filter = ("provider", "status")
    search_fields = ("display_name", "external_id", "user__username")
    raw_id_fields = ("user",)


@admin.register(ConnectorSyncRun)
class ConnectorSyncRunAdmin(admin.ModelAdmin):
    list_display = ("connection", "trigger", "status", "created_count", "rejected_count", "started_at")
    list_filter = ("trigger", "status")
    raw_id_fields = ("connection",)
    readonly_fields = (
        "correlation_id",
        "started_at",
        "finished_at",
        "received_count",
        "created_count",
        "updated_count",
        "skipped_count",
        "rejected_count",
        "error_code",
        "public_message",
        "cursor_before",
        "cursor_after",
    )


@admin.register(MaintenanceRun)
class MaintenanceRunAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "trigger",
        "status",
        "include_network",
        "connector_failure_count",
        "started_at",
    )
    list_filter = ("trigger", "status", "include_network")
    raw_id_fields = ("user",)
    readonly_fields = (
        "correlation_id",
        "started_at",
        "finished_at",
        "snapshot_created_count",
        "snapshot_existing_count",
        "virtual_portfolio_count",
        "virtual_order_executed_count",
        "virtual_order_rejected_count",
        "market_refresh_count",
        "market_failure_count",
        "fx_refresh_succeeded",
        "connector_run_count",
        "connector_failure_count",
        "public_message",
        "details",
    )


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "category", "currency", "balance", "status", "source")
    list_filter = ("category", "currency", "status", "source")
    search_fields = ("name", "external_id", "user__username")
    raw_id_fields = ("user", "connection")


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "ticker", "isin", "instrument_type", "currency")
    list_filter = ("instrument_type", "currency", "country_code")
    search_fields = ("name", "ticker", "isin", "contract_address")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("instrument", "account", "quantity", "current_value", "value_currency", "valued_at")
    list_filter = ("source", "value_currency")
    search_fields = ("instrument__name", "instrument__ticker", "account__name")
    raw_id_fields = ("account", "instrument")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("executed_at", "user", "account", "transaction_type", "net_amount", "currency", "status")
    list_filter = ("transaction_type", "status", "source", "currency")
    search_fields = ("label", "external_id", "idempotency_key", "account__name")
    raw_id_fields = ("user", "account", "instrument", "linked_transfer")
    date_hierarchy = "executed_at"


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("instrument", "close_price", "currency", "observed_at", "source", "quality")
    list_filter = ("source", "quality", "currency", "is_delayed")
    search_fields = ("instrument__name", "instrument__ticker")
    raw_id_fields = ("instrument",)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("base_currency", "quote_currency", "rate", "rate_date", "source", "quality")
    list_filter = ("source", "quality", "base_currency", "quote_currency")
    date_hierarchy = "rate_date"


@admin.register(MarketDataPreference)
class MarketDataPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "reporting_currency",
        "equity_display_currency",
        "crypto_display_currency",
        "benchmark_symbol",
    )
    raw_id_fields = ("user", "benchmark_instrument")


@admin.register(MarketDataStatus)
class MarketDataStatusAdmin(admin.ModelAdmin):
    list_display = (
        "instrument",
        "user",
        "provider",
        "state",
        "last_succeeded_at",
        "last_price_at",
    )
    list_filter = ("provider", "state")
    raw_id_fields = ("instrument", "user")


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("observed_at", "user", "scope", "converted_value", "converted_currency", "source")
    list_filter = ("scope", "source", "converted_currency")
    raw_id_fields = ("user", "account", "position")
    date_hierarchy = "observed_at"


@admin.register(ExternalIdentifier)
class ExternalIdentifierAdmin(admin.ModelAdmin):
    list_display = ("provider", "external_id", "user", "account", "instrument", "connection")
    list_filter = ("provider",)
    search_fields = ("external_id", "user__username")
    raw_id_fields = ("user", "account", "instrument", "connection")


admin.site.register(Subscription)
admin.site.register(Income)
admin.site.register(Watchlist)
admin.site.register(WatchInstrument)
admin.site.register(Notification)
admin.site.register(Loan)
admin.site.register(LoanBalanceSnapshot)
admin.site.register(LoanSimulationScenario)
admin.site.register(RealEstate)
admin.site.register(RealEstateValuation)
admin.site.register(PrivateEquityHolding)
admin.site.register(PrivateEquityValuation)
admin.site.register(CompoundInterestScenario)
admin.site.register(VirtualPortfolio)
admin.site.register(VirtualWatchlistEntry)
admin.site.register(VirtualPosition)
admin.site.register(VirtualOrder)
admin.site.register(VirtualCashEvent)
admin.site.register(VirtualCorporateAction)
admin.site.register(VirtualPortfolioSnapshot)
admin.site.register(FinancialAuditEvent)


class ImportIssueInline(admin.TabularInline):
    model = ImportIssue
    extra = 0
    readonly_fields = ("sheet", "row_number", "column", "code", "message", "value_preview")
    can_delete = False


class ImportChangeInline(admin.TabularInline):
    model = ImportChange
    extra = 0
    readonly_fields = (
        "sheet",
        "row_number",
        "model_name",
        "object_pk",
        "action",
        "before_data",
        "after_data",
    )
    can_delete = False


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "file_name",
        "user",
        "file_format",
        "status",
        "created_rows",
        "updated_rows",
        "invalid_rows",
        "started_at",
    )
    list_filter = ("file_format", "status")
    search_fields = ("file_name", "file_sha256", "user__username")
    raw_id_fields = ("user",)
    readonly_fields = (
        "file_sha256",
        "total_rows",
        "created_rows",
        "updated_rows",
        "skipped_rows",
        "invalid_rows",
        "started_at",
        "completed_at",
        "rolled_back_at",
    )
    inlines = (ImportIssueInline, ImportChangeInline)

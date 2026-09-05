from django.urls import path

from .view_modules.assets import (
    AddLoanBalanceModal,
    AddPrivateEquityModal,
    AddPrivateEquityValuationModal,
    AddRealEstateValuationModal,
    ArchivePrivateEquityModal,
    EditPrivateEquityModal,
    LoanDetailView,
    PrivateEquityDetailView,
    PrivateEquityView,
    RealEstateDetailView,
)
from .view_modules.connectors import (
    ConnectionDetailView,
    ConnectionDisconnectView,
    ConnectionImportView,
    ConnectionsView,
    ConnectionSyncView,
    ConnectionTestView,
    EnableBankingAuthorizeView,
    EnableBankingCallbackView,
)
from .view_modules.data_transfer import (
    ExcelTemplateView,
    ExportView,
    ImportBatchDetailView,
    ImportExportView,
    ImportIssuesCsvView,
    JsonTemplateView,
    RollbackImportView,
)
from .view_modules.manual import (
    AddInstrumentModal,
    AddLoanModal,
    AddPositionModal,
    AddRealEstateModal,
    AddTransactionModal,
    ArchiveInstrumentModal,
    ArchiveLoanModal,
    ArchivePositionModal,
    ArchiveRealEstateModal,
    CancelTransactionModal,
    EditInstrumentModal,
    EditLoanModal,
    EditPositionModal,
    EditRealEstateModal,
    EditTransactionModal,
    InstrumentsView,
    LoansView,
    RealEstateView,
)
from .view_modules.market_data import (
    AccountDetailView,
    CreateSnapshotView,
    InstrumentDetailView,
    MarketSettingsView,
    RefreshBenchmarkView,
    RefreshFxView,
    RefreshInstrumentView,
)
from .view_modules.operations import OperationsView, RunLocalMaintenanceView
from .view_modules.paper_trading import (
    AddVirtualCorporateActionModal,
    AddVirtualPortfolioModal,
    AddVirtualWatchlistModal,
    ApplyVirtualCorporateActionView,
    ArchiveVirtualPortfolioModal,
    CancelVirtualOrderView,
    CloneVirtualPortfolioModal,
    CreateVirtualSnapshotView,
    EditVirtualPortfolioModal,
    PlaceVirtualOrderModal,
    ProcessVirtualOrdersView,
    RemoveVirtualWatchlistView,
    ResetVirtualPortfolioView,
    VirtualPortfolioDetailView,
    VirtualPortfolioExportView,
    VirtualPortfolioListView,
)
from .view_modules.simulations import (
    AddCompoundSimulationModal,
    AddLoanSimulationModal,
    ArchiveCompoundSimulationModal,
    ArchiveLoanSimulationModal,
    CompoundComparisonView,
    CompoundInterestDetailView,
    CompoundSimulationExportView,
    EditCompoundSimulationModal,
    EditLoanSimulationModal,
    LoanComparisonView,
    LoanSimulationDetailView,
    LoanSimulationExportView,
    SimulationListView,
)
from .views import (
    AccountSourceModal,
    AccountsView,
    AddAccountModal,
    AddSubscriptionModal,
    DeleteAccountModal,
    DeleteSubscriptionModal,
    EditAccountModal,
    EditSubscriptionModal,
    FundBoardView,
    PortfolioView,
    RevenuesView,
    SubscriptionsView,
    TransactionsView,
)

app_name = "fundboard"

urlpatterns = [
    path("", FundBoardView.as_view(), name="fundboard"),
    path("market/settings/", MarketSettingsView.as_view(), name="market_settings"),
    path("market/fx/refresh/", RefreshFxView.as_view(), name="refresh_fx"),
    path("market/benchmark/refresh/", RefreshBenchmarkView.as_view(), name="refresh_benchmark"),
    path("snapshots/create/", CreateSnapshotView.as_view(), name="create_snapshot"),
    path("portfolio/",     PortfolioView.as_view(),     name="portfolio"),
    path("transactions/",  TransactionsView.as_view(),  name="transactions"),
    path("transactions/add/modal/", AddTransactionModal.as_view(), name="add_transaction_modal"),
    path("transactions/<int:pk>/edit/modal/", EditTransactionModal.as_view(), name="edit_transaction_modal"),
    path("transactions/<int:pk>/cancel/modal/", CancelTransactionModal.as_view(), name="cancel_transaction_modal"),

    # Instruments et positions
    path("instruments/", InstrumentsView.as_view(), name="instruments"),
    path("instruments/<int:pk>/", InstrumentDetailView.as_view(), name="instrument_detail"),
    path(
        "instruments/<int:pk>/refresh/",
        RefreshInstrumentView.as_view(),
        name="refresh_instrument",
    ),
    path("instruments/add/modal/", AddInstrumentModal.as_view(), name="add_instrument_modal"),
    path("instruments/<int:pk>/edit/modal/", EditInstrumentModal.as_view(), name="edit_instrument_modal"),
    path("instruments/<int:pk>/archive/modal/", ArchiveInstrumentModal.as_view(), name="archive_instrument_modal"),
    path("positions/add/modal/", AddPositionModal.as_view(), name="add_position_modal"),
    path("positions/<int:pk>/edit/modal/", EditPositionModal.as_view(), name="edit_position_modal"),
    path("positions/<int:pk>/archive/modal/", ArchivePositionModal.as_view(), name="archive_position_modal"),

    # Immobilier et prêts
    path("real-estate/", RealEstateView.as_view(), name="real_estate"),
    path("real-estate/<int:pk>/", RealEstateDetailView.as_view(), name="real_estate_detail"),
    path("real-estate/<int:pk>/valuations/add/modal/", AddRealEstateValuationModal.as_view(), name="add_real_estate_valuation"),
    path("real-estate/add/modal/", AddRealEstateModal.as_view(), name="add_real_estate_modal"),
    path("real-estate/<int:pk>/edit/modal/", EditRealEstateModal.as_view(), name="edit_real_estate_modal"),
    path("real-estate/<int:pk>/archive/modal/", ArchiveRealEstateModal.as_view(), name="archive_real_estate_modal"),
    path("loans/", LoansView.as_view(), name="loans"),
    path("loans/<int:pk>/", LoanDetailView.as_view(), name="loan_detail"),
    path("loans/<int:pk>/balances/add/modal/", AddLoanBalanceModal.as_view(), name="add_loan_balance"),
    path("loans/add/modal/", AddLoanModal.as_view(), name="add_loan_modal"),
    path("loans/<int:pk>/edit/modal/", EditLoanModal.as_view(), name="edit_loan_modal"),
    path("loans/<int:pk>/archive/modal/", ArchiveLoanModal.as_view(), name="archive_loan_modal"),
    path("private-equity/", PrivateEquityView.as_view(), name="private_equity"),
    path("private-equity/add/modal/", AddPrivateEquityModal.as_view(), name="add_private_equity"),
    path("private-equity/<int:pk>/", PrivateEquityDetailView.as_view(), name="private_equity_detail"),
    path("private-equity/<int:pk>/edit/modal/", EditPrivateEquityModal.as_view(), name="edit_private_equity"),
    path("private-equity/<int:pk>/archive/modal/", ArchivePrivateEquityModal.as_view(), name="archive_private_equity"),
    path("private-equity/<int:pk>/valuations/add/modal/", AddPrivateEquityValuationModal.as_view(), name="add_private_equity_valuation"),

    # Simulations, strictement séparées du patrimoine réel
    path("simulations/", SimulationListView.as_view(), name="simulations"),
    path(
        "simulations/loans/compare/",
        LoanComparisonView.as_view(),
        name="loan_simulation_compare",
    ),
    path(
        "simulations/loans/add/modal/",
        AddLoanSimulationModal.as_view(),
        name="add_loan_simulation",
    ),
    path(
        "simulations/loans/<int:pk>/",
        LoanSimulationDetailView.as_view(),
        name="loan_simulation_detail",
    ),
    path(
        "simulations/loans/<int:pk>/edit/modal/",
        EditLoanSimulationModal.as_view(),
        name="edit_loan_simulation",
    ),
    path(
        "simulations/loans/<int:pk>/archive/modal/",
        ArchiveLoanSimulationModal.as_view(),
        name="archive_loan_simulation",
    ),
    path(
        "simulations/loans/<int:pk>/export/<str:file_format>/",
        LoanSimulationExportView.as_view(),
        name="loan_simulation_export",
    ),
    path(
        "simulations/compound/compare/",
        CompoundComparisonView.as_view(),
        name="compound_simulation_compare",
    ),
    path(
        "simulations/compound/add/modal/",
        AddCompoundSimulationModal.as_view(),
        name="add_compound_simulation",
    ),
    path(
        "simulations/compound/<int:pk>/",
        CompoundInterestDetailView.as_view(),
        name="compound_simulation_detail",
    ),
    path(
        "simulations/compound/<int:pk>/edit/modal/",
        EditCompoundSimulationModal.as_view(),
        name="edit_compound_simulation",
    ),
    path(
        "simulations/compound/<int:pk>/archive/modal/",
        ArchiveCompoundSimulationModal.as_view(),
        name="archive_compound_simulation",
    ),
    path(
        "simulations/compound/<int:pk>/export/<str:file_format>/",
        CompoundSimulationExportView.as_view(),
        name="compound_simulation_export",
    ),

    # Portefeuilles de paper trading, sans compte ni ordre réel
    path("virtual/", VirtualPortfolioListView.as_view(), name="virtual_portfolios"),
    path("virtual/add/modal/", AddVirtualPortfolioModal.as_view(), name="add_virtual_portfolio"),
    path("virtual/<int:pk>/", VirtualPortfolioDetailView.as_view(), name="virtual_portfolio_detail"),
    path("virtual/<int:pk>/edit/modal/", EditVirtualPortfolioModal.as_view(), name="edit_virtual_portfolio"),
    path("virtual/<int:pk>/archive/modal/", ArchiveVirtualPortfolioModal.as_view(), name="archive_virtual_portfolio"),
    path("virtual/<int:pk>/clone/modal/", CloneVirtualPortfolioModal.as_view(), name="clone_virtual_portfolio"),
    path("virtual/<int:pk>/reset/modal/", ResetVirtualPortfolioView.as_view(), name="reset_virtual_portfolio"),
    path("virtual/<int:pk>/orders/add/modal/", PlaceVirtualOrderModal.as_view(), name="place_virtual_order"),
    path("virtual/<int:pk>/orders/process/", ProcessVirtualOrdersView.as_view(), name="process_virtual_orders"),
    path("virtual/<int:pk>/orders/<int:order_pk>/cancel/", CancelVirtualOrderView.as_view(), name="cancel_virtual_order"),
    path("virtual/<int:pk>/watch/<int:instrument_pk>/add/modal/", AddVirtualWatchlistModal.as_view(), name="add_virtual_watchlist"),
    path("virtual/<int:pk>/watch/<int:entry_pk>/remove/", RemoveVirtualWatchlistView.as_view(), name="remove_virtual_watchlist"),
    path("virtual/<int:pk>/events/add/modal/", AddVirtualCorporateActionModal.as_view(), name="add_virtual_corporate_action"),
    path("virtual/<int:pk>/events/<int:action_pk>/apply/", ApplyVirtualCorporateActionView.as_view(), name="apply_virtual_corporate_action"),
    path("virtual/<int:pk>/snapshots/create/", CreateVirtualSnapshotView.as_view(), name="create_virtual_snapshot"),
    path("virtual/<int:pk>/export/<str:file_format>/", VirtualPortfolioExportView.as_view(), name="virtual_portfolio_export"),

    # Exploitation locale et journaux de maintenance
    path("operations/", OperationsView.as_view(), name="operations"),
    path(
        "operations/run-local/",
        RunLocalMaintenanceView.as_view(),
        name="run_local_maintenance",
    ),

    # Imports et exports
    path("data/", ImportExportView.as_view(), name="import_export"),
    path("data/imports/<int:pk>/", ImportBatchDetailView.as_view(), name="import_batch"),
    path("data/imports/<int:pk>/issues.csv", ImportIssuesCsvView.as_view(), name="import_issues_csv"),
    path("data/imports/<int:pk>/rollback/", RollbackImportView.as_view(), name="rollback_import"),
    path("data/templates/import-v1.json", JsonTemplateView.as_view(), name="import_template_json"),
    path("data/templates/import-v1.xlsx", ExcelTemplateView.as_view(), name="import_template_xlsx"),
    path("data/exports/<str:file_format>/", ExportView.as_view(), name="export"),

    # Abonnements
    path("subscriptions/",                   SubscriptionsView.as_view(),      name="subscriptions"),
    path("subscriptions/add/modal/",   AddSubscriptionModal.as_view(),  name="add_subscription_modal"),
    path("subscriptions/<int:pk>/edit/modal/", EditSubscriptionModal.as_view(), name="edit_subscription_modal"),
    path("subscriptions/<int:pk>/delete/modal/",   DeleteSubscriptionModal.as_view(), name="delete_subscription_modal"),

    # Revenus
    path("revenues/", RevenuesView.as_view(), name="revenues"),

    # Comptes
    path("accounts/", AccountsView.as_view(), name="accounts"),
    path("accounts/<int:pk>/", AccountDetailView.as_view(), name="account_detail"),
    path("accounts/add/select/",             AccountSourceModal.as_view(),  name="account_source_modal"),
    path("accounts/add/modal/",              AddAccountModal.as_view(),     name="add_account_modal"),
    path("accounts/<int:pk>/edit/modal/",    EditAccountModal.as_view(),    name="edit_account_modal"),
    path("accounts/<int:pk>/delete/modal/",  DeleteAccountModal.as_view(),  name="delete_account_modal"),

    # Connexions financières en lecture seule
    path("connections/", ConnectionsView.as_view(), name="connections"),
    path("connections/<int:pk>/", ConnectionDetailView.as_view(), name="connection_detail"),
    path("connections/<int:pk>/test/", ConnectionTestView.as_view(), name="connection_test"),
    path("connections/<int:pk>/sync/", ConnectionSyncView.as_view(), name="connection_sync"),
    path("connections/<int:pk>/import/", ConnectionImportView.as_view(), name="connection_import"),
    path("connections/<int:pk>/disconnect/", ConnectionDisconnectView.as_view(), name="connection_disconnect"),
    path("connections/<int:pk>/authorize/", EnableBankingAuthorizeView.as_view(), name="enable_banking_authorize"),
    path("connections/enable-banking/callback/", EnableBankingCallbackView.as_view(), name="enable_banking_callback"),
]

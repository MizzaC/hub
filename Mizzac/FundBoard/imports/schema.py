from collections import OrderedDict

from FundBoard.models import Account, Instrument, Loan, Position, RealEstate, Transaction

SCHEMA_VERSION = "1.0"
MAX_IMPORT_BYTES = 5 * 1024 * 1024

SHEETS = OrderedDict(
    [
        (
            "Accounts",
            {
                "json_key": "accounts",
                "required": {"manual_reference", "name", "category", "currency"},
                "columns": [
                    "manual_reference",
                    "name",
                    "category",
                    "subtype",
                    "balance",
                    "currency",
                    "ownership_share",
                    "iban_masked",
                    "status",
                ],
                "example": ["cash-main", "Compte principal", "CURRENT", "", 1250, "EUR", 100, "", "ACTIVE"],
            },
        ),
        (
            "Instruments",
            {
                "json_key": "instruments",
                "required": {"manual_reference", "name", "instrument_type", "currency"},
                "columns": [
                    "manual_reference",
                    "name",
                    "instrument_type",
                    "ticker",
                    "isin",
                    "market_mic",
                    "currency",
                    "country_code",
                    "sector",
                    "blockchain",
                    "contract_address",
                    "status",
                ],
                "example": ["etf-world", "ETF Monde", "ETF", "WORLD", "", "XPAR", "EUR", "FR", "", "", "", "ACTIVE"],
            },
        ),
        (
            "Positions",
            {
                "json_key": "positions",
                "required": {"account_reference", "instrument_reference", "quantity", "value_currency"},
                "columns": [
                    "account_reference",
                    "instrument_reference",
                    "quantity",
                    "average_unit_cost",
                    "cost_basis",
                    "current_unit_price",
                    "current_value",
                    "value_currency",
                    "valued_at",
                    "status",
                ],
                "example": ["cash-main", "etf-world", 2.5, 100, 250, 110, 275, "EUR", "2026-09-04T12:00:00+02:00", "ACTIVE"],
            },
        ),
        (
            "Transactions",
            {
                "json_key": "transactions",
                "required": {"account_reference", "transaction_type", "net_amount", "currency", "executed_at"},
                "columns": [
                    "account_reference",
                    "instrument_reference",
                    "transaction_type",
                    "subtype",
                    "quantity",
                    "unit_price",
                    "gross_amount",
                    "fees",
                    "taxes",
                    "net_amount",
                    "currency",
                    "executed_at",
                    "value_date",
                    "label",
                    "status",
                    "idempotency_key",
                ],
                "example": ["cash-main", "", "DEPOSIT", "", "", "", 100, 0, 0, 100, "EUR", "2026-09-04T12:00:00+02:00", "2026-09-04", "Versement", "BOOKED", "example-deposit-1"],
            },
        ),
        (
            "RealEstate",
            {
                "json_key": "real_estate",
                "required": {"manual_reference", "name", "property_type", "currency", "purchase_price", "estimated_value", "valuation_date"},
                "columns": [
                    "manual_reference",
                    "name",
                    "property_type",
                    "address",
                    "surface_sqm",
                    "ownership_share",
                    "currency",
                    "purchase_price",
                    "purchase_costs",
                    "renovation_costs",
                    "estimated_value",
                    "valuation_date",
                    "valuation_source",
                    "monthly_rent",
                    "monthly_charges",
                    "annual_property_tax",
                    "annual_insurance",
                    "annual_other_costs",
                    "vacancy_rate",
                    "loan_reference",
                ],
                "example": ["home", "Résidence principale", "APARTMENT", "", 65, 100, "EUR", 250000, 20000, 5000, 300000, "2026-09-04", "manual", 0, 200, 1200, 300, 0, 0, "mortgage-home"],
            },
        ),
        (
            "Loans",
            {
                "json_key": "loans",
                "required": {"manual_reference", "name", "loan_type", "currency", "original_principal", "outstanding_principal", "nominal_rate", "duration_months", "start_date"},
                "columns": [
                    "manual_reference",
                    "name",
                    "loan_type",
                    "account_reference",
                    "currency",
                    "original_principal",
                    "outstanding_principal",
                    "balance_date",
                    "nominal_rate",
                    "apr",
                    "duration_months",
                    "start_date",
                    "maturity_date",
                    "payment_amount",
                    "insurance_amount",
                    "insurance_rate",
                    "initial_fees",
                    "deferred_months",
                ],
                "example": ["mortgage-home", "Prêt immobilier", "AMORT_FIXED", "cash-main", "EUR", 200000, 175000, "2026-09-04", 1.5, 1.8, 240, "2022-01-01", "2041-12-31", 965, 25, "", 1000, 0],
            },
        ),
    ]
)

MODEL_CHOICES = {
    "Accounts": Account,
    "Instruments": Instrument,
    "Positions": Position,
    "Transactions": Transaction,
    "RealEstate": RealEstate,
    "Loans": Loan,
}

CHOICE_LISTS = {
    "account_category": [value for value, _ in Account.Type.choices],
    "account_status": [value for value, _ in Account.Status.choices],
    "instrument_type": [value for value, _ in Instrument.Type.choices],
    "instrument_status": [value for value, _ in Instrument.Status.choices],
    "position_status": [value for value, _ in Position.Status.choices],
    "transaction_type": [value for value, _ in Transaction.Type.choices],
    "transaction_status": [value for value, _ in Transaction.Status.choices],
    "property_type": [value for value, _ in RealEstate.Type.choices],
    "loan_type": [value for value, _ in Loan.Type.choices],
}

VALIDATION_COLUMNS = {
    ("Accounts", "category"): "account_category",
    ("Accounts", "status"): "account_status",
    ("Instruments", "instrument_type"): "instrument_type",
    ("Instruments", "status"): "instrument_status",
    ("Positions", "status"): "position_status",
    ("Transactions", "transaction_type"): "transaction_type",
    ("Transactions", "status"): "transaction_status",
    ("RealEstate", "property_type"): "property_type",
    ("Loans", "loan_type"): "loan_type",
}

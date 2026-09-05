"""Build a source-aware portfolio valuation exclusively from cached data."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from FundBoard.models import Account, Instrument, Loan, Position, PrivateEquityHolding, RealEstate

from .fx import ExchangeRateUnavailable, StoredRate, convert_with_stored_rate
from .valuation import apply_ownership_share, quantize_value


@dataclass(frozen=True)
class ValuationLine:
    category: str
    label: str
    original_value: Decimal
    original_currency: str
    converted_value: Decimal
    converted_currency: str
    rate: StoredRate
    source: str
    observed_at: date | datetime | None
    account: object | None = None
    position: object | None = None


@dataclass(frozen=True)
class PortfolioValuation:
    currency: str
    assets: Decimal
    liabilities: Decimal
    cash: Decimal
    investments: Decimal
    other_assets: Decimal
    net_worth: Decimal
    allocation: tuple
    lines: tuple
    issues: tuple
    valued_at: date | datetime | None

    @property
    def complete(self):
        return not self.issues


def _converted_line(
    *,
    amount,
    currency,
    target_currency,
    category,
    label,
    source,
    observed_at,
    ownership_share=Decimal("100"),
    account=None,
    position=None,
):
    owned = apply_ownership_share(amount, ownership_share)
    converted, rate = convert_with_stored_rate(owned, currency, target_currency)
    return ValuationLine(
        category=category,
        label=label,
        original_value=owned,
        original_currency=currency,
        converted_value=converted,
        converted_currency=target_currency,
        rate=rate,
        source=source,
        observed_at=observed_at,
        account=account,
        position=position,
    )


def _latest_observation(lines):
    observations = [line.observed_at for line in lines if line.observed_at]
    if not observations:
        return None

    # Manual valuations use dates while provider data uses aware datetimes.
    # Compare both without relying on Python's invalid date/datetime ordering.
    def comparison_key(value):
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.combine(value, time.min, tzinfo=UTC)

    return max(observations, key=comparison_key)


def build_portfolio_valuation(user, target_currency="EUR"):
    lines = []
    issues = []

    def append_line(**kwargs):
        try:
            lines.append(_converted_line(target_currency=target_currency, **kwargs))
        except ExchangeRateUnavailable as exc:
            issues.append(f"{kwargs['label']} : {exc}")

    accounts = Account.objects.filter(user=user, status=Account.Status.ACTIVE)
    for account in accounts:
        append_line(
            amount=account.balance,
            currency=account.currency,
            category="CASH",
            label=account.name,
            source=account.get_source_display(),
            observed_at=account.updated_at,
            ownership_share=account.ownership_share,
            account=account,
        )

    positions = (
        Position.objects.filter(
            account__user=user,
            account__status=Account.Status.ACTIVE,
            status=Position.Status.ACTIVE,
        )
        .select_related("account", "instrument")
    )
    for position in positions:
        if position.current_value is None:
            issues.append(f"{position.instrument.name} : valorisation absente.")
            continue
        category = (
            "CRYPTO"
            if position.instrument.instrument_type == Instrument.Type.CRYPTO
            else "SECURITIES"
        )
        append_line(
            amount=position.current_value,
            currency=position.value_currency,
            category=category,
            label=position.instrument.name,
            source=position.get_source_display(),
            observed_at=position.valued_at,
            ownership_share=position.account.ownership_share,
            position=position,
        )

    for property_asset in RealEstate.objects.filter(user=user, archived=False):
        append_line(
            amount=property_asset.estimated_value,
            currency=property_asset.currency,
            category="REAL_ESTATE",
            label=property_asset.name,
            source=property_asset.valuation_source,
            observed_at=property_asset.valuation_date,
            ownership_share=property_asset.ownership_share,
        )

    for holding in PrivateEquityHolding.objects.filter(user=user, archived=False):
        append_line(
            amount=holding.net_asset_value,
            currency=holding.currency,
            category="PRIVATE_EQUITY",
            label=holding.name,
            source="Valorisation private equity",
            observed_at=holding.valuation_date,
            ownership_share=holding.ownership_share,
        )

    for loan in Loan.objects.filter(user=user, archived=False):
        append_line(
            amount=loan.outstanding_principal,
            currency=loan.currency,
            category="LIABILITY",
            label=loan.name,
            source="Capital restant déclaré",
            observed_at=loan.updated_at,
        )

    buckets = {
        "CASH": Decimal("0"),
        "SECURITIES": Decimal("0"),
        "CRYPTO": Decimal("0"),
        "REAL_ESTATE": Decimal("0"),
        "PRIVATE_EQUITY": Decimal("0"),
        "LIABILITY": Decimal("0"),
    }
    for line in lines:
        buckets[line.category] += line.converted_value

    cash = quantize_value(buckets["CASH"])
    investments = quantize_value(
        buckets["SECURITIES"] + buckets["CRYPTO"] + buckets["PRIVATE_EQUITY"]
    )
    other_assets = quantize_value(buckets["REAL_ESTATE"])
    liabilities = quantize_value(buckets["LIABILITY"])
    assets = quantize_value(cash + investments + other_assets)
    allocation_labels = {
        "CASH": "Trésorerie",
        "SECURITIES": "Actions, ETF et fonds",
        "CRYPTO": "Cryptomonnaies",
        "REAL_ESTATE": "Immobilier",
        "PRIVATE_EQUITY": "Private equity",
    }
    allocation = tuple(
        (allocation_labels[key], quantize_value(buckets[key]))
        for key in allocation_labels
        if buckets[key] > 0
    )
    return PortfolioValuation(
        currency=target_currency,
        assets=assets,
        liabilities=liabilities,
        cash=cash,
        investments=investments,
        other_assets=other_assets,
        net_worth=quantize_value(assets - liabilities),
        allocation=allocation,
        lines=tuple(lines),
        issues=tuple(issues),
        valued_at=_latest_observation(lines),
    )

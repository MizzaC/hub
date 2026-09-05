"""Pure Decimal metrics for real estate, loans and private equity."""

from dataclasses import dataclass
from decimal import Decimal

from .valuation import apply_ownership_share, quantize_value

PERCENT = Decimal("100")
MONTHS_PER_YEAR = Decimal("12")
RATIO_QUANTUM = Decimal("0.0001")


def _percent(numerator, denominator):
    if denominator == 0:
        return None
    return (numerator / denominator * PERCENT).quantize(RATIO_QUANTUM)


def _multiple(numerator, denominator):
    if denominator == 0:
        return None
    return (numerator / denominator).quantize(RATIO_QUANTUM)


@dataclass(frozen=True)
class RealEstateMetrics:
    gross_value: Decimal
    acquisition_cost: Decimal
    remaining_debt: Decimal | None
    net_value: Decimal | None
    unrealized_gain: Decimal
    annual_gross_rent: Decimal
    annual_vacancy_loss: Decimal
    annual_costs: Decimal
    annual_net_income: Decimal
    gross_yield_percent: Decimal | None
    net_yield_percent: Decimal | None


def real_estate_metrics(property_asset):
    share = property_asset.ownership_share
    gross_value = apply_ownership_share(property_asset.estimated_value, share)
    acquisition_cost = apply_ownership_share(
        property_asset.purchase_price
        + property_asset.purchase_costs
        + property_asset.renovation_costs,
        share,
    )
    annual_gross_rent = apply_ownership_share(
        property_asset.monthly_rent * MONTHS_PER_YEAR,
        share,
    )
    annual_vacancy_loss = quantize_value(
        annual_gross_rent * property_asset.vacancy_rate / PERCENT
    )
    annual_costs = apply_ownership_share(
        property_asset.monthly_charges * MONTHS_PER_YEAR
        + property_asset.annual_property_tax
        + property_asset.annual_insurance
        + property_asset.annual_other_costs,
        share,
    )
    annual_net_income = quantize_value(
        annual_gross_rent - annual_vacancy_loss - annual_costs
    )
    remaining_debt = Decimal("0")
    if property_asset.linked_loan_id:
        if property_asset.linked_loan.currency != property_asset.currency:
            remaining_debt = None
        else:
            remaining_debt = quantize_value(property_asset.linked_loan.outstanding_principal)
    net_value = (
        quantize_value(gross_value - remaining_debt)
        if remaining_debt is not None
        else None
    )
    return RealEstateMetrics(
        gross_value=quantize_value(gross_value),
        acquisition_cost=quantize_value(acquisition_cost),
        remaining_debt=remaining_debt,
        net_value=net_value,
        unrealized_gain=quantize_value(gross_value - acquisition_cost),
        annual_gross_rent=quantize_value(annual_gross_rent),
        annual_vacancy_loss=annual_vacancy_loss,
        annual_costs=quantize_value(annual_costs),
        annual_net_income=annual_net_income,
        gross_yield_percent=_percent(annual_gross_rent, acquisition_cost),
        net_yield_percent=_percent(annual_net_income, acquisition_cost),
    )


@dataclass(frozen=True)
class LoanMetrics:
    repaid_principal: Decimal
    progress_percent: Decimal
    remaining_percent: Decimal
    annual_payment: Decimal | None
    annual_insurance: Decimal
    linked_property_count: int


def loan_metrics(loan):
    repaid = quantize_value(loan.original_principal - loan.outstanding_principal)
    progress = _percent(repaid, loan.original_principal) or Decimal("0")
    remaining = _percent(loan.outstanding_principal, loan.original_principal) or Decimal("0")
    return LoanMetrics(
        repaid_principal=repaid,
        progress_percent=progress,
        remaining_percent=remaining,
        annual_payment=(
            quantize_value(loan.payment_amount * MONTHS_PER_YEAR)
            if loan.payment_amount is not None
            else None
        ),
        annual_insurance=quantize_value(loan.insurance_amount * MONTHS_PER_YEAR),
        linked_property_count=loan.properties.count(),
    )


@dataclass(frozen=True)
class PrivateEquityMetrics:
    commitment: Decimal
    called_capital: Decimal
    unfunded_commitment: Decimal
    distributions: Decimal
    net_asset_value: Decimal
    total_value: Decimal
    gain: Decimal
    called_percent: Decimal | None
    dpi: Decimal | None
    rvpi: Decimal | None
    tvpi: Decimal | None


def private_equity_metrics(holding):
    share = holding.ownership_share
    commitment = apply_ownership_share(holding.commitment, share)
    called = apply_ownership_share(holding.called_capital, share)
    distributions = apply_ownership_share(holding.distributions, share)
    nav = apply_ownership_share(holding.net_asset_value, share)
    return PrivateEquityMetrics(
        commitment=quantize_value(commitment),
        called_capital=quantize_value(called),
        unfunded_commitment=quantize_value(commitment - called),
        distributions=quantize_value(distributions),
        net_asset_value=quantize_value(nav),
        total_value=quantize_value(nav + distributions),
        gain=quantize_value(nav + distributions - called),
        called_percent=_percent(called, commitment),
        dpi=_multiple(distributions, called),
        rvpi=_multiple(nav, called),
        tvpi=_multiple(nav + distributions, called),
    )


def totals_by_currency(items, metrics_factory, fields):
    totals = {}
    for item in items:
        currency_totals = totals.setdefault(
            item.currency,
            {field: Decimal("0") for field in fields},
        )
        metrics = metrics_factory(item)
        for field in fields:
            value = getattr(metrics, field)
            if value is not None:
                currency_totals[field] += value
    return tuple(
        (currency, {field: quantize_value(value) for field, value in values.items()})
        for currency, values in sorted(totals.items())
    )

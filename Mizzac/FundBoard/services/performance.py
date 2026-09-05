"""Pure performance calculations with explicit cash-flow classification."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .valuation import as_decimal, quantize_value

RETURN_QUANTUM = Decimal("0.00000001")


class FlowKind(StrEnum):
    EXTERNAL = "external"
    INTERNAL = "internal"
    INCOME = "income"
    FEE = "fee"
    TAX = "tax"
    FX = "fx"
    MARKET = "market"


@dataclass(frozen=True)
class PerformanceFlow:
    amount: Decimal
    occurred_on: date
    kind: FlowKind

    def __post_init__(self):
        object.__setattr__(self, "amount", as_decimal(self.amount, field="flow.amount"))


@dataclass(frozen=True)
class PerformanceResult:
    absolute_gain: Decimal
    return_rate: Decimal
    external_flows: Decimal
    market_gain: Decimal
    income: Decimal
    fees: Decimal
    taxes: Decimal
    fx_effect: Decimal


def _sum_kind(flows, kind):
    return quantize_value(
        sum((flow.amount for flow in flows if flow.kind == kind), start=Decimal("0"))
    )


def modified_dietz(start_value, end_value, start_date, end_date, flows=()):
    """Calculate Modified Dietz performance for a closed period.

    External contributions are positive and withdrawals negative. Internal
    transfers are excluded at portfolio level. Income, fees, taxes, market and
    FX effects remain components of investment performance.
    """
    start = as_decimal(start_value, field="start_value")
    end = as_decimal(end_value, field="end_value")
    if end_date <= start_date:
        raise ValueError("La date de fin doit être postérieure à la date de début.")

    normalized_flows = tuple(flows)
    for flow in normalized_flows:
        if flow.occurred_on < start_date or flow.occurred_on > end_date:
            raise ValueError("Tous les flux doivent appartenir à la période calculée.")

    external = tuple(flow for flow in normalized_flows if flow.kind == FlowKind.EXTERNAL)
    external_total = sum((flow.amount for flow in external), start=Decimal("0"))
    days = Decimal((end_date - start_date).days)
    weighted_flows = sum(
        (
            flow.amount
            * Decimal((end_date - flow.occurred_on).days)
            / days
            for flow in external
        ),
        start=Decimal("0"),
    )
    denominator = start + weighted_flows
    if denominator == 0:
        raise ValueError("Le capital pondéré est nul ; la performance est indéfinie.")

    absolute_gain = quantize_value(end - start - external_total)
    income = _sum_kind(normalized_flows, FlowKind.INCOME)
    fees = _sum_kind(normalized_flows, FlowKind.FEE)
    taxes = _sum_kind(normalized_flows, FlowKind.TAX)
    fx_effect = _sum_kind(normalized_flows, FlowKind.FX)
    market_gain = quantize_value(absolute_gain - income - fees - taxes - fx_effect)
    return PerformanceResult(
        absolute_gain=absolute_gain,
        return_rate=(absolute_gain / denominator).quantize(
            RETURN_QUANTUM,
            rounding=ROUND_HALF_UP,
        ),
        external_flows=quantize_value(external_total),
        market_gain=market_gain,
        income=income,
        fees=fees,
        taxes=taxes,
        fx_effect=fx_effect,
    )

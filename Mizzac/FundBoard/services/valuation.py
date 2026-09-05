"""Pure, deterministic portfolio valuation helpers.

All public functions reject binary floats and return explicitly rounded Decimal
values. A liability is supplied as a positive amount and subtracted from net
worth; negative asset values remain possible for overdrafts.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

VALUE_QUANTUM = Decimal("0.00000001")
RATE_QUANTUM = Decimal("0.000000000001")
PERCENT = Decimal("100")


def as_decimal(value, *, field="value"):
    """Convert safe decimal inputs without silently accepting binary floats."""
    if isinstance(value, float):
        raise TypeError(f"{field} doit être fourni en Decimal, entier ou chaîne.")
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} n'est pas un nombre décimal valide.") from exc


def normalize_currency(currency):
    normalized = currency.strip().upper()
    if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
        raise ValueError("La devise doit être un code ISO sur trois lettres.")
    return normalized


def quantize_value(value):
    return as_decimal(value).quantize(VALUE_QUANTUM, rounding=ROUND_HALF_UP)


def position_market_value(quantity, unit_price):
    """Return quantity × price at the canonical eight-decimal value precision."""
    return quantize_value(
        as_decimal(quantity, field="quantity") * as_decimal(unit_price, field="unit_price")
    )


def convert_value(amount, source_currency, target_currency, rate=None):
    """Convert an amount with a direct source/target rate.

    The identity conversion always uses rate 1. Cross-currency conversion
    requires a strictly positive explicit rate; no live provider is called.
    """
    source = normalize_currency(source_currency)
    target = normalize_currency(target_currency)
    decimal_amount = as_decimal(amount, field="amount")
    if source == target:
        if rate is not None and as_decimal(rate, field="rate") != 1:
            raise ValueError("Une conversion dans la même devise doit utiliser le taux 1.")
        return quantize_value(decimal_amount)
    if rate is None:
        raise ValueError(f"Taux {source}/{target} manquant.")
    decimal_rate = as_decimal(rate, field="rate")
    if decimal_rate <= 0:
        raise ValueError("Le taux de change doit être strictement positif.")
    return quantize_value(decimal_amount * decimal_rate)


def apply_ownership_share(amount, share_percent):
    share = as_decimal(share_percent, field="share_percent")
    if share <= 0 or share > PERCENT:
        raise ValueError("La quote-part doit être supérieure à 0 et inférieure ou égale à 100.")
    return quantize_value(as_decimal(amount, field="amount") * share / PERCENT)


class ValuationKind(StrEnum):
    CASH = "cash"
    INVESTMENT = "investment"
    LIABILITY = "liability"
    OTHER_ASSET = "other_asset"


@dataclass(frozen=True)
class ValuationItem:
    amount: Decimal
    currency: str
    kind: ValuationKind
    ownership_share: Decimal = Decimal("100")

    def __post_init__(self):
        object.__setattr__(self, "amount", as_decimal(self.amount, field="amount"))
        object.__setattr__(self, "currency", normalize_currency(self.currency))
        object.__setattr__(
            self,
            "ownership_share",
            as_decimal(self.ownership_share, field="ownership_share"),
        )
        if self.ownership_share <= 0 or self.ownership_share > PERCENT:
            raise ValueError("Quote-part de valorisation invalide.")


@dataclass(frozen=True)
class ValuationTotals:
    currency: str
    assets: Decimal
    liabilities: Decimal
    cash: Decimal
    investments: Decimal
    other_assets: Decimal
    net_worth: Decimal


@dataclass(frozen=True)
class AppliedRate:
    base_currency: str
    quote_currency: str
    rate: Decimal
    rate_date: date

    def __post_init__(self):
        object.__setattr__(self, "base_currency", normalize_currency(self.base_currency))
        object.__setattr__(self, "quote_currency", normalize_currency(self.quote_currency))
        decimal_rate = as_decimal(self.rate, field="rate").quantize(
            RATE_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        if decimal_rate <= 0:
            raise ValueError("Le taux de change doit être strictement positif.")
        object.__setattr__(self, "rate", decimal_rate)


def summarize_valuation(items, target_currency, rates=()):
    """Aggregate owned values in one currency using explicit dated rates."""
    target = normalize_currency(target_currency)
    rate_map = {
        (rate.base_currency, rate.quote_currency): rate.rate
        for rate in rates
    }
    buckets = {
        ValuationKind.CASH: Decimal("0"),
        ValuationKind.INVESTMENT: Decimal("0"),
        ValuationKind.LIABILITY: Decimal("0"),
        ValuationKind.OTHER_ASSET: Decimal("0"),
    }
    for item in items:
        owned = apply_ownership_share(item.amount, item.ownership_share)
        rate = rate_map.get((item.currency, target))
        converted = convert_value(owned, item.currency, target, rate)
        buckets[item.kind] += converted

    cash = quantize_value(buckets[ValuationKind.CASH])
    investments = quantize_value(buckets[ValuationKind.INVESTMENT])
    other_assets = quantize_value(buckets[ValuationKind.OTHER_ASSET])
    liabilities = quantize_value(buckets[ValuationKind.LIABILITY])
    assets = quantize_value(cash + investments + other_assets)
    return ValuationTotals(
        currency=target,
        assets=assets,
        liabilities=liabilities,
        cash=cash,
        investments=investments,
        other_assets=other_assets,
        net_worth=quantize_value(assets - liabilities),
    )

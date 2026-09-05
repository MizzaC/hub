"""Prepare EUR/USD values for the shared client-side display toggle."""

from dataclasses import dataclass
from decimal import Decimal

from .fx import ExchangeRateUnavailable, convert_with_stored_rate
from .valuation import normalize_currency, quantize_value


@dataclass(frozen=True)
class CurrencyDisplay:
    original_amount: Decimal
    original_currency: str
    default_currency: str
    amount_eur: Decimal | None
    amount_usd: Decimal | None
    rate: Decimal = Decimal("1")
    rate_date: object | None = None
    rate_source: str = ""
    rate_quality: str = ""

    @property
    def original_amount_data(self):
        return format(self.original_amount, "f")

    @property
    def amount_eur_data(self):
        return format(self.amount_eur, "f") if self.amount_eur is not None else ""

    @property
    def amount_usd_data(self):
        return format(self.amount_usd, "f") if self.amount_usd is not None else ""


def prepare_currency_display(amount, currency, default_currency):
    source = normalize_currency(currency)
    default = normalize_currency(default_currency)
    original = quantize_value(amount)
    amounts = {source: original}
    applied = None
    for target in ("EUR", "USD"):
        if target in amounts:
            continue
        try:
            converted, rate = convert_with_stored_rate(original, source, target)
        except ExchangeRateUnavailable:
            continue
        amounts[target] = converted
        applied = rate
    return CurrencyDisplay(
        original_amount=original,
        original_currency=source,
        default_currency=default if default in amounts else source,
        amount_eur=amounts.get("EUR"),
        amount_usd=amounts.get("USD"),
        rate=applied.rate if applied else Decimal("1"),
        rate_date=applied.rate_date if applied else None,
        rate_source=applied.source if applied else "identity",
        rate_quality=applied.quality if applied else "FRESH",
    )

"""Persisted, dated FX rates; no calculation in this module calls the network."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from FundBoard.integrations.market_data.frankfurter import FrankfurterProvider
from FundBoard.models import ExchangeRate

from .valuation import RATE_QUANTUM, convert_value, normalize_currency


class ExchangeRateUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class StoredRate:
    base_currency: str
    quote_currency: str
    rate: Decimal
    rate_date: date
    source: str
    quality: str


def refresh_exchange_rate(base_currency="EUR", quote_currency="USD", *, provider=None):
    """Fetch once, then atomically store the direct and inverse ECB rates."""
    adapter = provider or FrankfurterProvider()
    quote = adapter.latest(base_currency, quote_currency)
    inverse = (Decimal("1") / quote.rate).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)
    collected_at = timezone.now()
    rows = (
        (quote.base_currency, quote.quote_currency, quote.rate),
        (quote.quote_currency, quote.base_currency, inverse),
    )
    stored = []
    with transaction.atomic():
        for base, target, rate in rows:
            instance, _ = ExchangeRate.objects.update_or_create(
                base_currency=base,
                quote_currency=target,
                rate_date=quote.rate_date,
                source=quote.source,
                defaults={
                    "rate": rate,
                    "collected_at": collected_at,
                    "quality": ExchangeRate.Quality.FRESH,
                },
            )
            stored.append(instance)
    return tuple(stored)


def _effective_quality(rate, *, today=None):
    comparison_date = today or timezone.localdate()
    if rate.quality == ExchangeRate.Quality.ERROR:
        return ExchangeRate.Quality.ERROR
    # Four calendar days cover a normal weekend without presenting an old rate as fresh.
    if (comparison_date - rate.rate_date).days > 4:
        return ExchangeRate.Quality.STALE
    return ExchangeRate.Quality.FRESH


def get_stored_rate(base_currency, quote_currency, *, on_date=None):
    """Return a direct stored rate, deriving the inverse only when necessary."""
    base = normalize_currency(base_currency)
    quote = normalize_currency(quote_currency)
    if base == quote:
        effective_date = on_date or timezone.localdate()
        return StoredRate(base, quote, Decimal("1"), effective_date, "identity", "FRESH")

    queryset = ExchangeRate.objects.filter(base_currency=base, quote_currency=quote)
    if on_date:
        queryset = queryset.filter(rate_date__lte=on_date)
    direct = queryset.order_by("-rate_date", "-collected_at").first()
    if direct:
        return StoredRate(
            base,
            quote,
            direct.rate,
            direct.rate_date,
            direct.source,
            _effective_quality(direct),
        )

    reverse_queryset = ExchangeRate.objects.filter(base_currency=quote, quote_currency=base)
    if on_date:
        reverse_queryset = reverse_queryset.filter(rate_date__lte=on_date)
    reverse = reverse_queryset.order_by("-rate_date", "-collected_at").first()
    if not reverse:
        raise ExchangeRateUnavailable(f"Taux {base}/{quote} indisponible.")
    inverse = (Decimal("1") / reverse.rate).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)
    return StoredRate(
        base,
        quote,
        inverse,
        reverse.rate_date,
        reverse.source,
        _effective_quality(reverse),
    )


def convert_with_stored_rate(amount, source_currency, target_currency, *, on_date=None):
    applied_rate = get_stored_rate(source_currency, target_currency, on_date=on_date)
    converted = convert_value(
        amount,
        applied_rate.base_currency,
        applied_rate.quote_currency,
        applied_rate.rate,
    )
    return converted, applied_rate

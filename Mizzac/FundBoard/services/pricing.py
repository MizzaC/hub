"""Orchestrate explicit provider refreshes into the canonical price cache."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from FundBoard.integrations.market_data.base import MarketDataError, MarketQuote
from FundBoard.integrations.market_data.registry import (
    get_provider,
    provider_identifier,
    provider_name_for,
)
from FundBoard.models import (
    Instrument,
    MarketDataPreference,
    MarketDataStatus,
    Position,
    Price,
)

from .display_currency import prepare_currency_display
from .valuation import position_market_value


def user_can_access_instrument(user, instrument):
    return Instrument.objects.filter(pk=instrument.pk).filter(
        Q(owner=user)
        | Q(owner__isnull=True, positions__account__user=user)
        | Q(benchmark_preferences__user=user)
        | Q(virtual_watchlist_entries__portfolio__user=user)
    ).exists()


def effective_price_state(instrument, price, *, now=None):
    if price is None or price.quality == Price.Quality.ERROR:
        return MarketDataStatus.State.ERROR
    current = now or timezone.now()
    maximum_age = (
        timedelta(hours=2)
        if instrument.instrument_type == Instrument.Type.CRYPTO
        else timedelta(days=4)
    )
    if current - price.observed_at > maximum_age:
        return MarketDataStatus.State.STALE
    return MarketDataStatus.State.FRESH


def latest_price(instrument):
    return instrument.prices.order_by("-observed_at", "-collected_at").first()


def _save_price(instrument, quote, *, market_state=None, market_timezone=None):
    if quote.close <= 0:
        raise MarketDataError("Le cours fournisseur doit être strictement positif.")
    lookup = {
        "instrument": instrument,
        "observed_at": quote.observed_at,
        "source": quote.source,
    }
    instance = Price.objects.filter(**lookup).first() or Price(**lookup)
    instance.open_price = quote.open_price
    instance.high_price = quote.high_price
    instance.low_price = quote.low_price
    instance.close_price = quote.close
    instance.volume = quote.volume
    instance.currency = quote.currency
    instance.collected_at = quote.collected_at
    instance.is_delayed = quote.is_delayed
    instance.quality = Price.Quality.FRESH
    instance.market_state = market_state or quote.market_state
    instance.market_timezone = market_timezone or quote.market_timezone
    instance.full_clean()
    instance.save()
    return instance


def _update_positions(user, instrument, quote):
    preference, _ = MarketDataPreference.objects.get_or_create(user=user)
    default_currency = (
        preference.crypto_display_currency
        if instrument.instrument_type == Instrument.Type.CRYPTO
        else preference.equity_display_currency
    )
    updated = 0
    positions = Position.objects.filter(
        account__user=user,
        instrument=instrument,
        status=Position.Status.ACTIVE,
    )
    for position in positions:
        current_value = position_market_value(position.quantity, quote.close)
        display = prepare_currency_display(current_value, quote.currency, default_currency)
        position.current_unit_price = quote.close
        position.current_value = current_value
        position.value_currency = quote.currency
        position.valued_at = quote.observed_at
        position.source = Position.Source.PROVIDER
        if display.default_currency == quote.currency:
            position.converted_value = current_value
            position.converted_currency = quote.currency
            position.exchange_rate = 1
            position.exchange_rate_date = quote.observed_at.date()
        else:
            converted = (
                display.amount_eur
                if display.default_currency == "EUR"
                else display.amount_usd
            )
            if converted is None:
                position.converted_value = None
                position.converted_currency = ""
                position.exchange_rate = None
                position.exchange_rate_date = None
            else:
                position.converted_value = converted
                position.converted_currency = display.default_currency
                position.exchange_rate = display.rate
                position.exchange_rate_date = display.rate_date
        position.full_clean()
        position.save(
            update_fields=[
                "current_unit_price",
                "current_value",
                "value_currency",
                "converted_value",
                "converted_currency",
                "exchange_rate",
                "exchange_rate_date",
                "valued_at",
                "source",
                "updated_at",
            ]
        )
        updated += 1
    return updated


def _status(user, instrument, provider_name):
    status, _ = MarketDataStatus.objects.get_or_create(
        user=user,
        instrument=instrument,
        provider=provider_name,
    )
    return status


def refresh_instrument_market_data(
    user,
    instrument,
    *,
    provider=None,
    include_history=True,
    history_days=365,
):
    """Refresh one owned/held instrument while preserving the last good cache on error."""
    if not user_can_access_instrument(user, instrument):
        raise PermissionError("Instrument inaccessible pour cet utilisateur.")
    adapter = provider or get_provider(provider_name_for(instrument))
    identifier = provider_identifier(instrument, adapter.name)
    status = _status(user, instrument, adapter.name)
    status.last_attempted_at = timezone.now()
    status.save(update_fields=["last_attempted_at", "updated_at"])
    quote_currency = "USD" if instrument.instrument_type == Instrument.Type.CRYPTO else None

    try:
        quote = adapter.latest(identifier, quote_currency=quote_currency)
        history = []
        if include_history:
            end = timezone.now()
            start = end - timedelta(days=history_days)
            history = adapter.history(
                identifier,
                start=start,
                end=end,
                quote_currency=quote_currency,
            )
        with transaction.atomic():
            for bar in history:
                historical_quote = MarketQuote(
                    provider_id=identifier,
                    symbol=quote.symbol,
                    close=bar.close,
                    currency=bar.currency,
                    observed_at=bar.observed_at,
                    collected_at=quote.collected_at,
                    source=quote.source,
                    open_price=bar.open_price,
                    high_price=bar.high_price,
                    low_price=bar.low_price,
                    volume=bar.volume,
                    is_delayed=True,
                    market_state=Price.MarketState.CLOSED,
                    market_timezone=quote.market_timezone,
                )
                _save_price(instrument, historical_quote)
            stored = _save_price(instrument, quote)
            if instrument.currency != quote.currency:
                instrument.currency = quote.currency
                instrument.save(update_fields=["currency", "updated_at"])
            positions_updated = _update_positions(user, instrument, quote)
            status.state = effective_price_state(instrument, stored)
            status.last_succeeded_at = timezone.now()
            status.last_price_at = stored.observed_at
            status.last_error = ""
            status.save(
                update_fields=[
                    "state",
                    "last_succeeded_at",
                    "last_price_at",
                    "last_error",
                    "updated_at",
                ]
            )
        return stored, positions_updated, len(history)
    except Exception as exc:
        status.state = MarketDataStatus.State.ERROR
        status.last_error = str(exc)[:500]
        status.save(update_fields=["state", "last_error", "updated_at"])
        if isinstance(exc, (MarketDataError, PermissionError)):
            raise
        raise MarketDataError("Actualisation du cours impossible.") from exc


def ensure_benchmark_instrument(preference):
    symbol = preference.benchmark_symbol.strip().upper()
    instrument, _ = Instrument.objects.get_or_create(
        owner=preference.user,
        manual_reference=f"system:benchmark:{symbol}",
        defaults={
            "name": f"Benchmark {symbol}",
            "instrument_type": Instrument.Type.INDEX,
            "ticker": symbol,
            "currency": preference.reporting_currency,
            "provider_identifiers": {"yahoo": symbol},
            "metadata": {"system_managed": True, "purpose": "benchmark"},
        },
    )
    if preference.benchmark_instrument_id != instrument.pk:
        preference.benchmark_instrument = instrument
        preference.save(update_fields=["benchmark_instrument", "updated_at"])
    return instrument

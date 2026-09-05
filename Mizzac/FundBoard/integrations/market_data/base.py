"""Provider-neutral market-data values.

Adapters convert provider numbers to ``Decimal`` at their boundary. Domain
services never receive a binary float and never perform network calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from django.utils import timezone


class MarketDataError(RuntimeError):
    """A provider failed or returned data that cannot be trusted."""


class MarketDataCapability(StrEnum):
    SEARCH = "search"
    LATEST = "latest"
    HISTORY = "history"
    EVENTS = "events"


def decimal_from_provider(value, *, field):
    """Normalize one external numeric value without retaining a float."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MarketDataError(f"Valeur fournisseur invalide pour {field}.") from exc
    if not result.is_finite():
        raise MarketDataError(f"Valeur fournisseur invalide pour {field}.")
    return result


def aware_utc(value):
    """Return an aware UTC instant for a provider timestamp."""
    if not isinstance(value, datetime):
        raise MarketDataError("Horodatage fournisseur invalide.")
    if timezone.is_naive(value):
        value = timezone.make_aware(value, UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class InstrumentSearchResult:
    provider_id: str
    symbol: str
    name: str
    instrument_type: str
    currency: str = ""
    exchange: str = ""


@dataclass(frozen=True)
class MarketQuote:
    provider_id: str
    symbol: str
    close: Decimal
    currency: str
    observed_at: datetime
    collected_at: datetime
    source: str
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    volume: Decimal | None = None
    is_delayed: bool = True
    market_state: str = "UNKNOWN"
    market_timezone: str = ""


@dataclass(frozen=True)
class HistoricalBar:
    observed_at: datetime
    close: Decimal
    currency: str
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    volume: Decimal | None = None


@dataclass(frozen=True)
class MarketEvent:
    occurred_on: date
    event_type: str
    value: Decimal
    currency: str = ""


class MarketDataProvider(ABC):
    name: str
    capabilities: frozenset[MarketDataCapability]

    @abstractmethod
    def search(self, query, *, limit=10):
        raise NotImplementedError

    @abstractmethod
    def latest(self, provider_id, *, quote_currency=None):
        raise NotImplementedError

    @abstractmethod
    def history(self, provider_id, *, start, end, quote_currency=None):
        raise NotImplementedError

    @abstractmethod
    def events(self, provider_id, *, start, end):
        raise NotImplementedError

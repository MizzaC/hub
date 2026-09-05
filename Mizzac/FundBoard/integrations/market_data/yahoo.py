"""Replaceable yfinance/Yahoo adapter for personal market-data use."""

from datetime import datetime

from django.utils import timezone

from .base import (
    HistoricalBar,
    InstrumentSearchResult,
    MarketDataCapability,
    MarketDataError,
    MarketDataProvider,
    MarketEvent,
    MarketQuote,
    aware_utc,
    decimal_from_provider,
)


def _optional_decimal(value, field):
    if value is None:
        return None
    try:
        result = decimal_from_provider(value, field=field)
    except MarketDataError:
        return None
    return result


def _currency_code(value):
    code = str(value or "").strip()
    if code == "GBp":
        return "GBX"
    code = code.upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise MarketDataError("Devise Yahoo absente ou invalide.")
    return code


def _market_state(value):
    return {
        "PRE": "PRE",
        "PREPRE": "PRE",
        "REGULAR": "REGULAR",
        "POST": "POST",
        "POSTPOST": "POST",
        "CLOSED": "CLOSED",
    }.get(str(value or "").upper(), "UNKNOWN")


class YahooFinanceProvider(MarketDataProvider):
    name = "yahoo"
    capabilities = frozenset(MarketDataCapability)

    def __init__(self, *, module=None):
        self._injected_module = module

    def _module(self):
        if self._injected_module is not None:
            return self._injected_module
        try:
            import yfinance
        except ImportError as exc:
            raise MarketDataError("La dépendance yfinance n’est pas installée.") from exc
        return yfinance

    def search(self, query, *, limit=10):
        try:
            search = self._module().Search(query, max_results=limit, news_count=0)
            quotes = search.quotes
        except Exception as exc:
            raise MarketDataError("Recherche Yahoo indisponible.") from exc
        type_map = {
            "EQUITY": "STOCK",
            "ETF": "ETF",
            "MUTUALFUND": "FUND",
            "INDEX": "INDEX",
            "CRYPTOCURRENCY": "CRYPTO",
        }
        return [
            InstrumentSearchResult(
                provider_id=str(item.get("symbol", "")),
                symbol=str(item.get("symbol", "")),
                name=str(item.get("longname") or item.get("shortname") or item.get("symbol", "")),
                instrument_type=type_map.get(str(item.get("quoteType", "")).upper(), "OTHER"),
                currency=str(item.get("currency", "")).upper(),
                exchange=str(item.get("exchange", "")),
            )
            for item in quotes
            if item.get("symbol")
        ]

    def _ticker_history(self, provider_id, **kwargs):
        try:
            ticker = self._module().Ticker(provider_id)
            frame = ticker.history(
                auto_adjust=False,
                repair=True,
                raise_errors=True,
                **kwargs,
            )
            metadata = ticker.history_metadata or {}
        except Exception as exc:
            raise MarketDataError(f"Cours Yahoo indisponible pour {provider_id}.") from exc
        if frame is None or frame.empty:
            raise MarketDataError(f"Aucun cours Yahoo disponible pour {provider_id}.")
        return frame, metadata

    def latest(self, provider_id, *, quote_currency=None):
        frame, metadata = self._ticker_history(
            provider_id,
            period="5d",
            interval="1d",
            actions=False,
        )
        row = frame.iloc[-1]
        timestamp = frame.index[-1]
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if not isinstance(timestamp, datetime):
            raise MarketDataError("Horodatage Yahoo invalide.")
        currency = _currency_code(metadata.get("currency"))
        return MarketQuote(
            provider_id=provider_id,
            symbol=provider_id,
            close=decimal_from_provider(row.get("Close"), field="close"),
            open_price=_optional_decimal(row.get("Open"), "open"),
            high_price=_optional_decimal(row.get("High"), "high"),
            low_price=_optional_decimal(row.get("Low"), "low"),
            volume=_optional_decimal(row.get("Volume"), "volume"),
            currency=currency,
            observed_at=aware_utc(timestamp),
            collected_at=timezone.now(),
            source=self.name,
            # Yahoo/yfinance does not guarantee a real-time licensed feed.
            is_delayed=True,
            market_state=_market_state(metadata.get("marketState")),
            market_timezone=str(metadata.get("exchangeTimezoneName", "")),
        )

    def history(self, provider_id, *, start, end, quote_currency=None):
        frame, metadata = self._ticker_history(
            provider_id,
            start=start,
            end=end,
            interval="1d",
            actions=False,
        )
        currency = _currency_code(metadata.get("currency"))
        bars = []
        for timestamp, row in frame.iterrows():
            if hasattr(timestamp, "to_pydatetime"):
                timestamp = timestamp.to_pydatetime()
            bars.append(
                HistoricalBar(
                    observed_at=aware_utc(timestamp),
                    close=decimal_from_provider(row.get("Close"), field="close"),
                    currency=currency,
                    open_price=_optional_decimal(row.get("Open"), "open"),
                    high_price=_optional_decimal(row.get("High"), "high"),
                    low_price=_optional_decimal(row.get("Low"), "low"),
                    volume=_optional_decimal(row.get("Volume"), "volume"),
                )
            )
        return bars

    def events(self, provider_id, *, start, end):
        frame, metadata = self._ticker_history(
            provider_id,
            start=start,
            end=end,
            interval="1d",
            actions=True,
        )
        currency = _currency_code(metadata.get("currency"))
        events = []
        for timestamp, row in frame.iterrows():
            occurred_on = timestamp.date()
            dividend = _optional_decimal(row.get("Dividends"), "dividend")
            split = _optional_decimal(row.get("Stock Splits"), "split")
            if dividend and dividend != 0:
                events.append(MarketEvent(occurred_on, "DIVIDEND", dividend, currency))
            if split and split != 0:
                events.append(MarketEvent(occurred_on, "SPLIT", split))
        return events

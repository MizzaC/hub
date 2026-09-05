"""CoinGecko adapter for public, read-only cryptocurrency market data."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote

import requests
from django.utils import timezone

from .base import (
    HistoricalBar,
    InstrumentSearchResult,
    MarketDataCapability,
    MarketDataError,
    MarketDataProvider,
    MarketQuote,
    aware_utc,
    decimal_from_provider,
)

REQUEST_TIMEOUT = (3.05, 15)


class CoinGeckoProvider(MarketDataProvider):
    name = "coingecko"
    endpoint = "https://api.coingecko.com/api/v3"
    capabilities = frozenset(
        {
            MarketDataCapability.SEARCH,
            MarketDataCapability.LATEST,
            MarketDataCapability.HISTORY,
        }
    )

    def __init__(self, *, api_key="", http_get=None):
        self.api_key = api_key
        self.http_get = http_get or requests.get

    def _get(self, path, *, params=None):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key
        try:
            response = self.http_get(
                f"{self.endpoint}{path}",
                params=params or {},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return json.loads(response.text, parse_float=Decimal)
        except (requests.RequestException, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise MarketDataError("Données CoinGecko indisponibles.") from exc

    def search(self, query, *, limit=10):
        payload = self._get("/search", params={"query": query})
        results = []
        for item in payload.get("coins", [])[:limit]:
            provider_id = str(item.get("id", "")).strip()
            if not provider_id:
                continue
            results.append(
                InstrumentSearchResult(
                    provider_id=provider_id,
                    symbol=str(item.get("symbol", "")).upper(),
                    name=str(item.get("name", provider_id)),
                    instrument_type="CRYPTO",
                    currency="USD",
                    exchange="CoinGecko",
                )
            )
        return results

    def latest(self, provider_id, *, quote_currency=None):
        currency = (quote_currency or "USD").lower()
        safe_id = quote(provider_id, safe="")
        payload = self._get(
            "/simple/price",
            params={
                "ids": provider_id,
                "vs_currencies": currency,
                "include_last_updated_at": "true",
                "precision": "full",
            },
        )
        try:
            item = payload[provider_id]
            close = decimal_from_provider(item[currency], field="close")
            timestamp = int(item["last_updated_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(f"Cours CoinGecko introuvable pour {safe_id}.") from exc
        observed_at = aware_utc(datetime.fromtimestamp(timestamp, tz=UTC))
        return MarketQuote(
            provider_id=provider_id,
            symbol=provider_id,
            close=close,
            currency=currency.upper(),
            observed_at=observed_at,
            collected_at=timezone.now(),
            source=self.name,
            is_delayed=True,
            market_timezone="UTC",
        )

    def history(self, provider_id, *, start, end, quote_currency=None):
        currency = (quote_currency or "USD").lower()
        safe_id = quote(provider_id, safe="")
        payload = self._get(
            f"/coins/{safe_id}/market_chart/range",
            params={
                "vs_currency": currency,
                "from": int(start.timestamp()),
                "to": int(end.timestamp()),
                "precision": "full",
            },
        )
        bars = []
        for timestamp_ms, value in payload.get("prices", []):
            observed_at = datetime.fromtimestamp(
                int(Decimal(str(timestamp_ms)) / Decimal("1000")),
                tz=UTC,
            )
            bars.append(
                HistoricalBar(
                    observed_at=aware_utc(observed_at),
                    close=decimal_from_provider(value, field="close"),
                    currency=currency.upper(),
                )
            )
        return bars

    def events(self, provider_id, *, start, end):
        return []

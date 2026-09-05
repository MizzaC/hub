"""Frankfurter v2 adapter pinned to official ECB reference rates."""

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import requests

from FundBoard.services.valuation import normalize_currency

from .base import MarketDataError, decimal_from_provider

REQUEST_TIMEOUT = (3.05, 10)


@dataclass(frozen=True)
class FxRateQuote:
    base_currency: str
    quote_currency: str
    rate: Decimal
    rate_date: date
    source: str = "frankfurter-ecb"


class FrankfurterProvider:
    name = "frankfurter-ecb"
    endpoint = "https://api.frankfurter.dev/v2"

    def __init__(self, *, http_get=None):
        self.http_get = http_get or requests.get

    def latest(self, base_currency, quote_currency):
        base = normalize_currency(base_currency)
        quote = normalize_currency(quote_currency)
        if base == quote:
            raise MarketDataError("Frankfurter exige deux devises différentes.")
        try:
            response = self.http_get(
                f"{self.endpoint}/rate/{base}/{quote}",
                params={"providers": "ECB"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = json.loads(response.text, parse_float=Decimal)
            payload_base = normalize_currency(payload["base"])
            payload_quote = normalize_currency(payload["quote"])
            rate = decimal_from_provider(payload["rate"], field="rate")
            rate_date = date.fromisoformat(payload["date"])
        except (
            requests.RequestException,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise MarketDataError("Taux Frankfurter/ECB indisponible.") from exc
        if payload_base != base or payload_quote != quote or rate <= 0:
            raise MarketDataError("Réponse Frankfurter/ECB incohérente.")
        return FxRateQuote(base, quote, rate, rate_date)

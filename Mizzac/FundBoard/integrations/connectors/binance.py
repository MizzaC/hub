"""Minimal Binance Spot connector exposing only read-only HTTP operations."""

import hashlib
import hmac
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode

import requests

from .base import (
    ConnectionCheck,
    ConnectorError,
    ConnectorProvider,
    RemoteAccount,
    RemoteInstrument,
    RemotePosition,
    RemoteTransaction,
    SyncPayload,
    decimal_value,
)
from .secrets import resolve_secrets

SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")
FIAT_OR_STABLE = {
    "EUR": "EUR",
    "USD": "USD",
    "GBP": "GBP",
    "CHF": "CHF",
    "JPY": "JPY",
    "CAD": "CAD",
    "AUD": "AUD",
    "USDT": "USD",
    "USDC": "USD",
    "FDUSD": "USD",
}
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "ADA": "cardano",
    "XRP": "ripple",
    "DOT": "polkadot",
    "LINK": "chainlink",
}


class BinanceConnector(ConnectorProvider):
    key = "binance"
    label = "Binance Spot"
    base_url = "https://api.binance.com"

    def __init__(self, *, session=None, clock=None, sleeper=None):
        self.session = session or requests.Session()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper or time.sleep
        self._clock_offset_ms = 0

    def validate_configuration(self, configuration):
        symbols = configuration.get("symbols", ["BTCUSDT", "ETHUSDT"])
        if isinstance(symbols, str):
            symbols = [item.strip().upper() for item in symbols.split(",") if item.strip()]
        if not symbols or len(symbols) > 20 or any(not SYMBOL_RE.fullmatch(item) for item in symbols):
            raise ConnectorError("invalid_configuration", "La liste de paires Binance est invalide.")
        initial_days = int(configuration.get("initial_days", 90))
        if not 1 <= initial_days <= 365:
            raise ConnectorError("invalid_configuration", "L'historique initial doit couvrir 1 à 365 jours.")
        return {"symbols": symbols, "initial_days": initial_days}

    def _request(self, path, *, params=None, signed=False, secrets=None):
        query = dict(params or {})
        headers = {}
        if signed:
            if not secrets:
                raise ConnectorError("missing_secret", "La clé Binance est absente.")
            query.update(
                {
                    "timestamp": int(self.clock().timestamp() * 1000) + self._clock_offset_ms,
                    "recvWindow": 5000,
                }
            )
            encoded = urlencode(query)
            query["signature"] = hmac.new(
                secrets["secret_key"].encode(), encoded.encode(), hashlib.sha256
            ).hexdigest()
            headers["X-MBX-APIKEY"] = secrets["api_key"]
        for attempt in range(3):
            try:
                response = self.session.get(
                    f"{self.base_url}{path}", params=query, headers=headers, timeout=(3.05, 15)
                )
            except requests.RequestException as exc:
                if attempt == 2:
                    raise ConnectorError("network", "Binance est momentanément inaccessible.") from exc
                self.sleeper(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise ConnectorError("provider_unavailable", "Binance limite ou refuse temporairement la requête.")
                retry_after = response.headers.get("Retry-After", "")
                self.sleeper(min(int(retry_after) if retry_after.isdigit() else 2**attempt, 5))
                continue
            if response.status_code >= 400:
                raise ConnectorError("provider_rejected", "Binance a refusé la requête en lecture.")
            try:
                return response.json()
            except ValueError as exc:
                raise ConnectorError("invalid_response", "Binance a renvoyé une réponse invalide.") from exc
        raise ConnectorError("provider_unavailable", "Binance est momentanément inaccessible.")

    def _sync_clock(self):
        payload = self._request("/api/v3/time")
        self._clock_offset_ms = int(payload["serverTime"]) - int(self.clock().timestamp() * 1000)

    def _account(self, connection):
        self._sync_clock()
        secrets = resolve_secrets(connection)
        return self._request("/api/v3/account", signed=True, secrets=secrets), secrets

    def test_connection(self, connection):
        self.validate_configuration(connection.configuration)
        account, _ = self._account(connection)
        if account.get("canTrade") or account.get("canWithdraw"):
            raise ConnectorError(
                "unsafe_permissions",
                "La clé Binance doit interdire le trading et les retraits.",
            )
        return ConnectionCheck(("balances", "positions", "trades"))

    def _symbol_info(self, symbol):
        payload = self._request("/api/v3/exchangeInfo", params={"symbol": symbol})
        try:
            item = payload["symbols"][0]
            return item["baseAsset"], item["quoteAsset"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ConnectorError("invalid_response", "Une paire Binance n'est pas reconnue.") from exc

    def _trade_pages(self, symbol, *, previous_id, initial_days, secrets):
        params = {"symbol": symbol, "limit": 1000}
        if previous_id is not None:
            params["fromId"] = int(previous_id) + 1
        else:
            params["startTime"] = int(
                (self.clock() - timedelta(days=initial_days)).timestamp() * 1000
            )
        collected = []
        for _ in range(50):
            page = self._request(
                "/api/v3/myTrades",
                params=params,
                signed=True,
                secrets=secrets,
            )
            if not isinstance(page, list):
                raise ConnectorError("invalid_response", "L'historique Binance est invalide.")
            collected.extend(page)
            if len(page) < 1000:
                return collected
            params.pop("startTime", None)
            params["fromId"] = max(int(item["id"]) for item in page) + 1
        raise ConnectorError("pagination_limit", "L'historique Binance dépasse la limite de sécurité.")

    def sync(self, connection):
        configuration = self.validate_configuration(connection.configuration)
        account_payload, secrets = self._account(connection)
        if account_payload.get("canTrade") or account_payload.get("canWithdraw"):
            raise ConnectorError("unsafe_permissions", "La clé Binance n'est pas strictement en lecture seule.")

        account = RemoteAccount(
            external_id="spot",
            name=connection.display_name or "Binance Spot",
            category="CRYPTO",
            currency="USD",
            balance=Decimal("0"),
            subtype="Spot",
        )
        instruments = []
        positions = []
        seen_assets = set()
        for balance in account_payload.get("balances", []):
            asset = str(balance.get("asset", "")).upper()
            try:
                quantity = decimal_value(balance.get("free", 0)) + decimal_value(balance.get("locked", 0))
            except ValueError:
                continue
            if not asset or quantity == 0:
                continue
            seen_assets.add(asset)
            identifiers = {"binance": asset}
            if asset in COINGECKO_IDS:
                identifiers["coingecko"] = COINGECKO_IDS[asset]
            instruments.append(
                RemoteInstrument(asset, asset, asset, "CRYPTO", "USD", identifiers)
            )
            positions.append(RemotePosition("spot", asset, quantity, "USD"))

        transactions = []
        issues = []
        previous = connection.sync_cursor.get("trades", {})
        next_trade_cursor = dict(previous)
        for symbol in configuration["symbols"]:
            base_asset, quote_asset = self._symbol_info(symbol)
            monetary_currency = FIAT_OR_STABLE.get(quote_asset)
            trades = self._trade_pages(
                symbol,
                previous_id=previous.get(symbol),
                initial_days=configuration["initial_days"],
                secrets=secrets,
            )
            if not monetary_currency and trades:
                issues.append(f"{symbol}: devise de cotation non monétaire, opérations ignorées")
                next_trade_cursor[symbol] = max(int(item["id"]) for item in trades)
                continue
            if base_asset not in seen_assets:
                identifiers = {"binance": base_asset}
                if base_asset in COINGECKO_IDS:
                    identifiers["coingecko"] = COINGECKO_IDS[base_asset]
                instruments.append(
                    RemoteInstrument(base_asset, base_asset, base_asset, "CRYPTO", "USD", identifiers)
                )
                seen_assets.add(base_asset)
            for item in trades:
                quantity = decimal_value(item["qty"], field_name="quantité")
                gross = decimal_value(item["quoteQty"], field_name="contre-valeur")
                fee_quantity = decimal_value(item.get("commission", 0), field_name="frais")
                fee_asset = str(item.get("commissionAsset", "")).upper()
                monetary_fee = fee_quantity if FIAT_OR_STABLE.get(fee_asset) == monetary_currency else Decimal("0")
                is_buy = bool(item.get("isBuyer"))
                net = -(gross + monetary_fee) if is_buy else gross - monetary_fee
                transactions.append(
                    RemoteTransaction(
                        external_id=f"trade:{symbol}:{item['id']}",
                        account_external_id="spot",
                        instrument_external_id=base_asset,
                        transaction_type="BUY" if is_buy else "SELL",
                        quantity=quantity,
                        unit_price=decimal_value(item["price"], field_name="prix"),
                        gross_amount=gross,
                        fees=monetary_fee,
                        net_amount=net,
                        currency=monetary_currency,
                        executed_at=datetime.fromtimestamp(int(item["time"]) / 1000, tz=timezone.utc),
                        label=f"{symbol} — {'achat' if is_buy else 'vente'}",
                        metadata={"settlement_asset": quote_asset, "fee_asset": fee_asset, "fee_quantity": str(fee_quantity)},
                    )
                )
            if trades:
                next_trade_cursor[symbol] = max(int(item["id"]) for item in trades)

        return SyncPayload(
            accounts=(account,),
            instruments=tuple(instruments),
            positions=tuple(positions),
            transactions=tuple(transactions),
            cursor={"trades": next_trade_cursor},
            issues=tuple(issues),
        )

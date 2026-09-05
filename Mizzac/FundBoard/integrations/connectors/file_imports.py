"""Offline import adapters for Ledger Live and Trade Republic exports."""

import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .base import (
    ConnectorError,
    ConnectorProvider,
    RemoteAccount,
    RemoteInstrument,
    RemotePosition,
    RemoteTransaction,
    SyncPayload,
    decimal_value,
)


def _identifier(*parts):
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:32]


def _pick(row, *names, default=""):
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower())
        if value not in (None, ""):
            return value
    return default


def _datetime(value):
    raw = str(value or "").strip().replace("Z", "+00:00")
    if not raw:
        raise ValueError("date absente")
    for parser in (
        lambda: datetime.fromisoformat(raw),
        lambda: datetime.strptime(raw, "%d/%m/%Y %H:%M:%S"),
        lambda: datetime.strptime(raw, "%d/%m/%Y"),
        lambda: datetime.strptime(raw, "%Y-%m-%d"),
    ):
        try:
            result = parser()
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError("date invalide")


def _csv_rows(content):
    text = content.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


class LedgerLiveImportConnector(ConnectorProvider):
    key = "ledger_live"
    label = "Ledger Live (import)"
    import_only = True

    def validate_configuration(self, configuration):
        return {}

    def parse(self, content, filename):
        if Path(filename).suffix.lower() != ".csv":
            raise ConnectorError("invalid_file", "Ledger Live attend un fichier CSV.")
        try:
            rows = _csv_rows(content)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ConnectorError("invalid_file", "Le CSV Ledger Live est illisible.") from exc
        accounts = {}
        instruments = {}
        quantities = defaultdict(lambda: 0)
        transactions = []
        issues = []
        for line_number, row in enumerate(rows, start=2):
            try:
                account_name = str(_pick(row, "Account Name", "account", "account_name")).strip()
                asset = str(_pick(row, "Currency Ticker", "currency ticker", "asset", "currency")).strip().upper()
                operation = str(_pick(row, "Operation Type", "type", "operation")).strip().lower()
                quantity = decimal_value(_pick(row, "Operation Amount", "amount", "quantity"), field_name="quantité")
                happened_at = _datetime(_pick(row, "Operation Date", "date", "timestamp"))
                if not account_name or not asset or len(asset) > 30 or quantity == 0:
                    raise ValueError("champs obligatoires absents")
                account_id = _identifier("ledger", account_name)
                accounts[account_id] = RemoteAccount(account_id, account_name[:255], "CRYPTO", "USD", decimal_value(0), subtype="Ledger Live")
                identifiers = {"ledger_live": asset}
                instruments[asset] = RemoteInstrument(asset, asset, asset, "CRYPTO", "USD", identifiers)
                signed_quantity = -abs(quantity) if operation in {"out", "send", "withdrawal", "fees"} else abs(quantity)
                quantities[(account_id, asset)] += signed_quantity

                countervalue = _pick(row, "Countervalue at Operation Date", "countervalue", "fiat_amount")
                fiat = str(_pick(row, "Countervalue Ticker", "countervalue ticker", "fiat_currency", default="USD")).upper()
                if countervalue not in (None, "") and len(fiat) == 3 and fiat.isalpha():
                    amount = abs(decimal_value(countervalue, field_name="contre-valeur"))
                    if amount:
                        transaction_type = "WITHDRAWAL" if signed_quantity < 0 else "DEPOSIT"
                        external_id = str(_pick(row, "Operation Hash", "hash", "transaction_id")) or _identifier(line_number, happened_at, account_id, asset, quantity)
                        transactions.append(
                            RemoteTransaction(
                                external_id=f"ledger:{external_id}",
                                account_external_id=account_id,
                                instrument_external_id=asset,
                                transaction_type=transaction_type,
                                quantity=abs(quantity),
                                net_amount=-amount if signed_quantity < 0 else amount,
                                currency=fiat,
                                executed_at=happened_at,
                                label=f"Ledger Live — {operation or 'opération'} {asset}",
                            )
                        )
            except (ValueError, TypeError, KeyError):
                issues.append(f"ligne {line_number}: invalide, non importée")
        positions = tuple(
            RemotePosition(account_id, asset, quantity, "USD")
            for (account_id, asset), quantity in quantities.items()
            if quantity != 0
        )
        return SyncPayload(tuple(accounts.values()), tuple(instruments.values()), positions, tuple(transactions), issues=tuple(issues))


class TradeRepublicImportConnector(ConnectorProvider):
    key = "trade_republic"
    label = "Trade Republic (import expérimental)"
    import_only = True

    def validate_configuration(self, configuration):
        if not configuration.get("experimental_accepted"):
            raise ConnectorError("acceptance_required", "Acceptez le caractère expérimental de cet import.")
        return {"experimental_accepted": True}

    @staticmethod
    def _json_rows(content):
        payload = json.loads(content.decode("utf-8-sig"))
        if isinstance(payload, dict):
            payload = payload.get("transactions") or payload.get("items") or payload.get("timelineTransactions")
        if not isinstance(payload, list):
            raise ValueError("liste absente")
        return payload

    def parse(self, content, filename):
        suffix = Path(filename).suffix.lower()
        try:
            rows = self._json_rows(content) if suffix == ".json" else _csv_rows(content)
        except (UnicodeDecodeError, csv.Error, json.JSONDecodeError, ValueError) as exc:
            raise ConnectorError("invalid_file", "L'export Trade Republic est illisible.") from exc
        if suffix not in {".json", ".csv"}:
            raise ConnectorError("invalid_file", "Utilisez un export JSON ou CSV.")
        account = RemoteAccount("trade-republic", "Trade Republic", "CTO", "EUR", decimal_value(0), subtype="Import local")
        transactions = []
        issues = []
        for line_number, raw in enumerate(rows, start=2):
            try:
                row = raw if isinstance(raw, dict) else {}
                amount_field = row.get("amount", "")
                if isinstance(amount_field, dict):
                    amount_raw = amount_field.get("value") or amount_field.get("amount")
                    currency = str(amount_field.get("currency", "EUR")).upper()
                else:
                    amount_raw = _pick(row, "amount.value", "amount", "net_amount")
                    currency = str(_pick(row, "amount.currency", "currency", default="EUR")).upper()
                amount = decimal_value(amount_raw)
                external_id = str(_pick(row, "id", "transaction_id", "timeline_id")).strip()
                happened_at = _datetime(_pick(row, "timestamp", "date", "executed_at"))
                title = str(_pick(row, "title", "body", "label", default="Opération Trade Republic"))[:500]
                if not external_id or amount == 0 or len(currency) != 3 or not currency.isalpha():
                    raise ValueError("ligne incomplète")
                lower_title = title.lower()
                if any(word in lower_title for word in ("dividend", "dividende", "interest", "intérêt")) and amount > 0:
                    kind = "DIVIDEND" if "dividend" in lower_title or "dividende" in lower_title else "INTEREST"
                else:
                    kind = "DEPOSIT" if amount > 0 else "WITHDRAWAL"
                transactions.append(
                    RemoteTransaction(
                        external_id=f"trade-republic:{external_id}",
                        account_external_id="trade-republic",
                        transaction_type=kind,
                        net_amount=amount,
                        currency=currency,
                        executed_at=happened_at,
                        label=title,
                    )
                )
            except (ValueError, TypeError, KeyError):
                issues.append(f"ligne {line_number}: invalide, non importée")
        return SyncPayload(accounts=(account,), transactions=tuple(transactions), issues=tuple(issues))

"""Enable Banking AIS connector for the user's own accounts."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .base import (
    ConnectionCheck,
    ConnectorError,
    OpenBankingProvider,
    RemoteAccount,
    RemoteTransaction,
    SyncPayload,
    decimal_value,
)
from .secrets import resolve_secrets


def mask_iban(value):
    compact = "".join(str(value or "").split()).upper()
    if len(compact) < 8:
        return ""
    return f"{compact[:4]} •••• {compact[-4:]}"


def _parse_datetime(value):
    if not value:
        return None
    normalized = str(value).replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            result = datetime.combine(date.fromisoformat(normalized), datetime.min.time())
        except ValueError as exc:
            raise ValueError("date fournisseur invalide") from exc
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


class EnableBankingConnector(OpenBankingProvider):
    key = "enable_banking"
    label = "Enable Banking"
    base_url = "https://api.enablebanking.com"

    def __init__(self, *, session=None, jwt_encoder=None, clock=None, key_loader=None):
        self.session = session or requests.Session()
        self.jwt_encoder = jwt_encoder
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.key_loader = key_loader or self._load_private_key

    def validate_configuration(self, configuration):
        bank_name = str(configuration.get("bank_name", "")).strip()
        country = str(configuration.get("country", "FR")).strip().upper()
        consent_days = int(configuration.get("consent_days", 180))
        if not bank_name or len(bank_name) > 100:
            raise ConnectorError("invalid_configuration", "Sélectionnez une banque Enable Banking.")
        if len(country) != 2 or not country.isalpha():
            raise ConnectorError("invalid_configuration", "Le pays de la banque est invalide.")
        if not 1 <= consent_days <= 180:
            raise ConnectorError("invalid_configuration", "Le consentement doit durer 1 à 180 jours.")
        return {"bank_name": bank_name, "country": country, "consent_days": consent_days}

    @staticmethod
    def _load_private_key(path):
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ConnectorError("missing_secret", "La clé privée Enable Banking est inaccessible.") from exc

    def _token(self, connection):
        secrets = resolve_secrets(connection)
        encoder = self.jwt_encoder
        if encoder is None:
            try:
                import jwt
            except ImportError as exc:
                raise ConnectorError("dependency", "Le support JWT Enable Banking n'est pas installé.") from exc
            encoder = jwt.encode
        now = int(self.clock().timestamp())
        claims = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": now,
            "exp": now + 3600,
        }
        try:
            return encoder(
                claims,
                self.key_loader(secrets["private_key_path"]),
                algorithm="RS256",
                headers={"kid": secrets["application_id"]},
            )
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError("invalid_secret", "La clé Enable Banking n'est pas valide.") from exc

    def _request(self, connection, method, path, *, body=None, params=None):
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=body,
                params=params,
                headers={"Authorization": f"Bearer {self._token(connection)}"},
                timeout=(3.05, 20),
            )
        except requests.RequestException as exc:
            raise ConnectorError("network", "Enable Banking est momentanément inaccessible.") from exc
        if response.status_code >= 400:
            raise ConnectorError("provider_rejected", "Enable Banking a refusé la requête.")
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError("invalid_response", "Enable Banking a renvoyé une réponse invalide.") from exc

    def start_authorization(self, connection, *, redirect_url, state):
        config = self.validate_configuration(connection.configuration)
        valid_until = (self.clock() + timedelta(days=config["consent_days"])).date().isoformat()
        payload = self._request(
            connection,
            "POST",
            "/auth",
            body={
                "access": {"valid_until": valid_until},
                "aspsp": {"name": config["bank_name"], "country": config["country"]},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": "personal",
            },
        )
        if not payload.get("url") or not payload.get("authorization_id"):
            raise ConnectorError("invalid_response", "L'autorisation bancaire n'a pas pu démarrer.")
        return payload["url"], payload["authorization_id"]

    def complete_authorization(self, connection, *, code):
        payload = self._request(connection, "POST", "/sessions", body={"code": code})
        session_id = str(payload.get("session_id", ""))
        if not session_id:
            raise ConnectorError("invalid_response", "La banque n'a pas créé de session de lecture.")
        return session_id, payload

    def test_connection(self, connection):
        self.validate_configuration(connection.configuration)
        if not connection.external_id:
            raise ConnectorError("consent_required", "Une autorisation bancaire est requise.")
        session = self._request(connection, "GET", f"/sessions/{connection.external_id}")
        expires = _parse_datetime(session.get("valid_until"))
        return ConnectionCheck(("accounts", "balances", "transactions"), expires)

    @staticmethod
    def _account_uid(item):
        account_id = item.get("account_id") or {}
        return str(item.get("uid") or account_id.get("uid") or item.get("id") or "")

    @staticmethod
    def _balance_value(payload):
        balances = payload.get("balances", payload if isinstance(payload, list) else [])
        priorities = {"CLBD": 0, "CLAV": 1, "ITAV": 2, "XPCD": 3}
        candidates = sorted(
            balances,
            key=lambda item: priorities.get(str(item.get("balance_type", "")), 99),
        )
        for item in candidates:
            amount = item.get("balance_amount") or item.get("amount") or {}
            if isinstance(amount, dict) and amount.get("amount") is not None:
                return decimal_value(amount["amount"]), str(amount.get("currency", "")).upper()
        raise ValueError("solde bancaire absent")

    @staticmethod
    def _transaction(item, account_uid, *, require_stable_id=False):
        amount = item.get("transaction_amount") or item.get("amount") or {}
        value = decimal_value(amount.get("amount"), field_name="montant")
        currency = str(amount.get("currency", "")).upper()
        if value == 0 or len(currency) != 3:
            raise ValueError("montant ou devise invalide")
        executed = _parse_datetime(item.get("booking_date") or item.get("value_date") or item.get("transaction_date"))
        if executed is None:
            raise ValueError("date bancaire absente")
        reference = str(item.get("entry_reference") or item.get("transaction_id") or "")
        if require_stable_id and not reference:
            raise ValueError("identifiant bancaire stable absent")
        if not reference:
            stable = json.dumps(
                [account_uid, str(value), currency, executed.isoformat(), item.get("remittance_information", "")],
                ensure_ascii=True,
            )
            reference = hashlib.sha256(stable.encode()).hexdigest()
        label_value = item.get("remittance_information") or item.get("creditor_name") or item.get("debtor_name") or "Opération bancaire"
        if isinstance(label_value, list):
            label_value = " ".join(str(part) for part in label_value)
        pending = str(item.get("status", "BOOK")).upper() in {"PDNG", "PENDING"}
        return RemoteTransaction(
            external_id=f"bank:{account_uid}:{reference}",
            account_external_id=account_uid,
            transaction_type="DEPOSIT" if value > 0 else "WITHDRAWAL",
            net_amount=value,
            currency=currency,
            executed_at=executed,
            value_date=_parse_datetime(item.get("value_date")).date() if item.get("value_date") else None,
            label=str(label_value)[:500],
            status="PENDING" if pending else "BOOKED",
        )

    def sync(self, connection):
        self.test_connection(connection)
        session_payload = self._request(connection, "GET", f"/sessions/{connection.external_id}")
        source_accounts = session_payload.get("accounts", [])
        accounts = []
        transactions = []
        issues = []
        cursor_accounts = {}
        for item in source_accounts:
            uid = self._account_uid(item)
            if not uid:
                issues.append("compte sans identifiant ignoré")
                continue
            try:
                details = self._request(connection, "GET", f"/accounts/{uid}/details")
                balance, currency = self._balance_value(
                    self._request(connection, "GET", f"/accounts/{uid}/balances")
                )
                identification = details.get("account_id") or item.get("account_id") or {}
                iban = identification.get("iban", "") if isinstance(identification, dict) else ""
                name = details.get("name") or details.get("product") or item.get("name") or "Compte bancaire"
                category = "SAVINGS" if "saving" in str(details.get("cash_account_type", "")).lower() else "CURRENT"
                accounts.append(RemoteAccount(uid, str(name)[:255], category, currency, balance, mask_iban(iban)))
            except (ConnectorError, ValueError, TypeError):
                issues.append(f"compte {uid}: données invalides")
                continue

            previous_date = connection.sync_cursor.get("accounts", {}).get(uid, "")
            date_from = previous_date or (self.clock().date() - timedelta(days=90)).isoformat()
            continuation = ""
            while True:
                params = {
                    "date_from": date_from,
                    "date_to": self.clock().date().isoformat(),
                }
                if continuation:
                    params["continuation_key"] = continuation
                page = self._request(connection, "GET", f"/accounts/{uid}/transactions", params=params)
                for operation in page.get("transactions", []):
                    try:
                        transactions.append(
                            self._transaction(
                                operation,
                                uid,
                                require_stable_id=connection.configuration.get(
                                    "requires_stable_transaction_id",
                                    False,
                                ),
                            )
                        )
                    except (ValueError, TypeError, KeyError):
                        issues.append(f"compte {uid}: opération invalide ignorée")
                continuation = str(page.get("continuation_key") or "")
                if not continuation:
                    break
            cursor_accounts[uid] = self.clock().date().isoformat()
        return SyncPayload(
            accounts=tuple(accounts),
            transactions=tuple(transactions),
            cursor={"accounts": cursor_accounts},
            issues=tuple(issues),
        )

    def revoke(self, connection):
        if connection.external_id:
            self._request(connection, "DELETE", f"/sessions/{connection.external_id}")

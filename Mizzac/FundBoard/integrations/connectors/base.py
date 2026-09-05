"""Provider-independent values returned by financial connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class ConnectorError(RuntimeError):
    """A failure safe to expose without leaking a provider payload or secret."""

    def __init__(self, code, public_message):
        self.code = code
        self.public_message = public_message
        super().__init__(public_message)


def decimal_value(value, *, field_name="montant"):
    try:
        result = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, AttributeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalide") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} invalide")
    return result


@dataclass(frozen=True)
class ConnectionCheck:
    capabilities: tuple[str, ...] = ()
    consent_expires_at: datetime | None = None


@dataclass(frozen=True)
class RemoteAccount:
    external_id: str
    name: str
    category: str
    currency: str
    balance: Decimal
    iban_masked: str = ""
    subtype: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteInstrument:
    external_id: str
    name: str
    ticker: str
    instrument_type: str
    currency: str
    provider_identifiers: dict = field(default_factory=dict)
    blockchain: str = ""
    contract_address: str = ""


@dataclass(frozen=True)
class RemotePosition:
    account_external_id: str
    instrument_external_id: str
    quantity: Decimal
    value_currency: str
    current_unit_price: Decimal | None = None
    current_value: Decimal | None = None
    valued_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteTransaction:
    external_id: str
    account_external_id: str
    transaction_type: str
    net_amount: Decimal
    currency: str
    executed_at: datetime
    instrument_external_id: str = ""
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    gross_amount: Decimal | None = None
    fees: Decimal = Decimal("0")
    value_date: date | None = None
    label: str = ""
    status: str = "BOOKED"
    subtype: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SyncPayload:
    accounts: tuple[RemoteAccount, ...] = ()
    instruments: tuple[RemoteInstrument, ...] = ()
    positions: tuple[RemotePosition, ...] = ()
    transactions: tuple[RemoteTransaction, ...] = ()
    cursor: dict = field(default_factory=dict)
    issues: tuple[str, ...] = ()


class ConnectorProvider(ABC):
    key = ""
    label = ""
    import_only = False

    @abstractmethod
    def validate_configuration(self, configuration):
        raise NotImplementedError

    def test_connection(self, connection):
        if self.import_only:
            return ConnectionCheck(("file_import",))
        raise NotImplementedError

    def sync(self, connection):
        raise NotImplementedError

    def revoke(self, connection):
        return None


class OpenBankingProvider(ConnectorProvider):
    """AIS-only consent contract; implementations never receive bank credentials."""

    @abstractmethod
    def start_authorization(self, connection, *, redirect_url, state):
        raise NotImplementedError

    @abstractmethod
    def complete_authorization(self, connection, *, code):
        raise NotImplementedError

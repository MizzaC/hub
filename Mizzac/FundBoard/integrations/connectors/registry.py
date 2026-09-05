from .base import ConnectorError
from .binance import BinanceConnector
from .enable_banking import EnableBankingConnector
from .file_imports import LedgerLiveImportConnector, TradeRepublicImportConnector

CONNECTORS = {
    "binance": BinanceConnector,
    "enable_banking": EnableBankingConnector,
    "ledger_live": LedgerLiveImportConnector,
    "trade_republic": TradeRepublicImportConnector,
}


def get_connector(provider, **kwargs):
    try:
        connector_class = CONNECTORS[provider]
    except KeyError as exc:
        raise ConnectorError("unknown_provider", "Ce fournisseur n'est pas pris en charge.") from exc
    return connector_class(**kwargs)

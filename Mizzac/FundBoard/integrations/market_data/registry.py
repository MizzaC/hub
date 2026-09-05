"""Small registry keeping provider selection out of views and models."""

from django.conf import settings

from FundBoard.models import Instrument

from .base import MarketDataError
from .coingecko import CoinGeckoProvider
from .yahoo import YahooFinanceProvider


def get_provider(name):
    normalized = name.strip().lower()
    if normalized == "yahoo":
        return YahooFinanceProvider()
    if normalized == "coingecko":
        return CoinGeckoProvider(api_key=settings.COINGECKO_API_KEY)
    raise MarketDataError(f"Fournisseur de marché inconnu : {normalized}.")


def provider_name_for(instrument):
    if instrument.instrument_type == Instrument.Type.CRYPTO:
        return settings.FUND_BOARD_CRYPTO_PROVIDER
    return settings.FUND_BOARD_EQUITY_PROVIDER


def provider_identifier(instrument, provider_name):
    identifier = instrument.provider_identifiers.get(provider_name)
    # CoinGecko IDs ("bitcoin") are not ticker symbols ("BTC") and must be
    # explicit to avoid silently retrieving the wrong asset.
    if not identifier and provider_name != "coingecko":
        identifier = instrument.ticker
    if not identifier:
        raise MarketDataError(
            f"Identifiant {provider_name} manquant pour {instrument.name}."
        )
    return str(identifier)

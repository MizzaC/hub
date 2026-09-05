"""Small converter backed by Frankfurter v2 and official ECB rates."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from FundBoard.integrations.market_data.base import MarketDataError
from FundBoard.integrations.market_data.frankfurter import REQUEST_TIMEOUT as REQUEST_TIMEOUT
from FundBoard.integrations.market_data.frankfurter import FrankfurterProvider

CENT = Decimal("0.01")


class CurrencyConversionError(Exception):
    """Raised when an exchange rate cannot be retrieved or validated."""


def _currency_code(value):
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise CurrencyConversionError("Code devise invalide.")
    return code


def convert_currency(amount, from_currency, to_currency, http_get=None):
    """Convert an amount with Decimal arithmetic and a bounded HTTP request."""
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CurrencyConversionError("Montant invalide.") from exc
    if not decimal_amount.is_finite():
        raise CurrencyConversionError("Montant invalide.")

    source = _currency_code(from_currency)
    target = _currency_code(to_currency)
    if source == target:
        return decimal_amount.quantize(CENT, rounding=ROUND_HALF_UP)

    try:
        rate = FrankfurterProvider(http_get=http_get).latest(source, target).rate
    except MarketDataError as exc:
        raise CurrencyConversionError("Taux de change indisponible.") from exc

    return (decimal_amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)

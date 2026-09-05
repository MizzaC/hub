"""Pure Decimal calculations for recurring cash flows."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DAYS_PER_YEAR = Decimal("365")
MONTHS_PER_YEAR = Decimal("12")
STANDARD_OCCURRENCES = {
    "DAILY": DAYS_PER_YEAR,
    "WEEKLY": Decimal("52"),
    "MONTHLY": MONTHS_PER_YEAR,
    "YEARLY": Decimal("1"),
}


@dataclass(frozen=True)
class RecurringTotals:
    monthly: Decimal
    yearly: Decimal


def annualized_amount(amount, frequency, custom_days=None):
    """Return a cent-rounded yearly equivalent without using binary floats."""
    decimal_amount = Decimal(amount)
    if frequency == "PERSONALIZED":
        if not custom_days or custom_days <= 0:
            raise ValueError("custom_days doit être un entier strictement positif.")
        occurrences = DAYS_PER_YEAR / Decimal(custom_days)
    else:
        try:
            occurrences = STANDARD_OCCURRENCES[frequency]
        except KeyError as exc:
            raise ValueError(f"Fréquence inconnue : {frequency}") from exc
    return (decimal_amount * occurrences).quantize(CENT, rounding=ROUND_HALF_UP)


def summarize_recurring(items):
    """Calculate monthly and yearly equivalents for recurring model instances."""
    yearly = sum(
        (
            annualized_amount(item.amount, item.freq, item.freq_custom)
            for item in items
        ),
        start=Decimal("0"),
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    monthly = (yearly / MONTHS_PER_YEAR).quantize(CENT, rounding=ROUND_HALF_UP)
    return RecurringTotals(monthly=monthly, yearly=yearly)


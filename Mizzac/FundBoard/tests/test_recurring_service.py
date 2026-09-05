from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from FundBoard.services.recurring import annualized_amount, summarize_recurring


class RecurringCalculationsTests(SimpleTestCase):
    def test_standard_annualized_amounts_use_decimal(self):
        self.assertEqual(annualized_amount("10.00", "DAILY"), Decimal("3650.00"))
        self.assertEqual(annualized_amount("10.00", "WEEKLY"), Decimal("520.00"))
        self.assertEqual(annualized_amount("10.00", "MONTHLY"), Decimal("120.00"))
        self.assertEqual(annualized_amount("10.00", "YEARLY"), Decimal("10.00"))

    def test_personalized_frequency_never_uses_binary_float(self):
        result = annualized_amount(Decimal("3.50"), "PERSONALIZED", custom_days=7)

        self.assertEqual(result, Decimal("182.50"))
        self.assertIsInstance(result, Decimal)

    def test_summary_returns_monthly_and_yearly_equivalents(self):
        items = [
            SimpleNamespace(
                amount=Decimal("12.50"),
                freq="MONTHLY",
                freq_custom=None,
            ),
            SimpleNamespace(
                amount=Decimal("3.50"),
                freq="PERSONALIZED",
                freq_custom=7,
            ),
        ]

        summary = summarize_recurring(items)

        self.assertEqual(summary.yearly, Decimal("332.50"))
        self.assertEqual(summary.monthly, Decimal("27.71"))

    def test_unknown_or_invalid_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            annualized_amount("10.00", "UNKNOWN")
        with self.assertRaises(ValueError):
            annualized_amount("10.00", "PERSONALIZED", custom_days=0)


from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from FundBoard.services.valuation import (
    AppliedRate,
    ValuationItem,
    ValuationKind,
    apply_ownership_share,
    convert_value,
    position_market_value,
    summarize_valuation,
)


class ValuationServiceTests(SimpleTestCase):
    def test_position_value_preserves_fractional_precision(self):
        value = position_market_value(
            Decimal("0.123456789012345678"),
            Decimal("123.123456789012"),
        )

        self.assertEqual(value, Decimal("15.20042663"))

    def test_conversion_and_ownership_are_explicitly_rounded(self):
        owned = apply_ownership_share(Decimal("123.456789"), Decimal("50"))
        converted = convert_value(owned, "USD", "EUR", Decimal("0.912345678901"))

        self.assertEqual(owned, Decimal("61.72839450"))
        self.assertEqual(converted, Decimal("56.31763399"))

    def test_summary_separates_assets_liabilities_and_classes(self):
        items = [
            ValuationItem(Decimal("1000"), "EUR", ValuationKind.CASH),
            ValuationItem(Decimal("500"), "USD", ValuationKind.INVESTMENT),
            ValuationItem(
                Decimal("200"),
                "EUR",
                ValuationKind.OTHER_ASSET,
                ownership_share=Decimal("50"),
            ),
            ValuationItem(Decimal("300"), "EUR", ValuationKind.LIABILITY),
        ]
        rate = AppliedRate("USD", "EUR", Decimal("0.9"), date(2026, 9, 4))

        result = summarize_valuation(items, "EUR", rates=[rate])

        self.assertEqual(result.cash, Decimal("1000.00000000"))
        self.assertEqual(result.investments, Decimal("450.00000000"))
        self.assertEqual(result.other_assets, Decimal("100.00000000"))
        self.assertEqual(result.assets, Decimal("1550.00000000"))
        self.assertEqual(result.liabilities, Decimal("300.00000000"))
        self.assertEqual(result.net_worth, Decimal("1250.00000000"))

    def test_cross_currency_conversion_requires_a_rate(self):
        with self.assertRaisesRegex(ValueError, "Taux USD/EUR manquant"):
            convert_value(Decimal("10"), "USD", "EUR")

    def test_binary_float_is_rejected(self):
        with self.assertRaises(TypeError):
            position_market_value(0.1, Decimal("10"))

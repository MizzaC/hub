from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ToolBoard.services.currency import (
    REQUEST_TIMEOUT,
    CurrencyConversionError,
    convert_currency,
)


class CurrencyServiceTests(SimpleTestCase):
    def test_conversion_uses_decimal_status_check_and_timeout(self):
        response = Mock()
        response.text = '{"date":"2026-09-04","base":"EUR","quote":"USD","rate":1.2345}'
        http_get = Mock(return_value=response)

        result = convert_currency("10.00", "eur", "usd", http_get=http_get)

        self.assertEqual(result, Decimal("12.35"))
        http_get.assert_called_once_with(
            "https://api.frankfurter.dev/v2/rate/EUR/USD",
            params={"providers": "ECB"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status.assert_called_once_with()

    def test_invalid_payload_is_reported_as_domain_error(self):
        response = Mock()
        response.text = "{}"

        with self.assertRaises(CurrencyConversionError):
            convert_currency("10.00", "EUR", "USD", http_get=Mock(return_value=response))


class CurrencyConverterViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="currency-user")

    def setUp(self):
        self.client.force_login(self.user)

    @patch("ToolBoard.views.convert_currency", return_value=Decimal("12.35"))
    def test_view_delegates_conversion_without_real_network(self, convert_mock):
        response = self.client.post(
            reverse("toolboard:currency_converter"),
            {"amount": "10.00", "from_currency": "EUR", "to_currency": "USD"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result"], Decimal("12.35"))
        convert_mock.assert_called_once_with("10.00", "EUR", "USD")

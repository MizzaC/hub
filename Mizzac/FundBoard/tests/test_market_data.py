import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from FundBoard.integrations.market_data.base import MarketDataError, MarketQuote
from FundBoard.integrations.market_data.coingecko import CoinGeckoProvider
from FundBoard.integrations.market_data.frankfurter import FrankfurterProvider
from FundBoard.integrations.market_data.registry import provider_identifier
from FundBoard.integrations.market_data.yahoo import YahooFinanceProvider
from FundBoard.models import (
    Account,
    ExchangeRate,
    Instrument,
    MarketDataPreference,
    MarketDataStatus,
    Position,
    Price,
    RealEstate,
    Snapshot,
)
from FundBoard.services.display_currency import prepare_currency_display
from FundBoard.services.fx import get_stored_rate, refresh_exchange_rate
from FundBoard.services.net_worth import build_portfolio_valuation
from FundBoard.services.pricing import refresh_instrument_market_data
from FundBoard.services.snapshots import IncompleteValuationError, create_daily_snapshots


def response_with(payload):
    response = Mock()
    response.text = json.dumps(payload)
    return response


class ProviderContractTests(SimpleTestCase):
    def test_frankfurter_is_pinned_to_ecb_and_parses_decimal(self):
        http_get = Mock(
            return_value=response_with(
                {"date": "2026-09-04", "base": "EUR", "quote": "USD", "rate": 1.1622}
            )
        )

        result = FrankfurterProvider(http_get=http_get).latest("eur", "usd")

        self.assertEqual(result.rate, Decimal("1.1622"))
        self.assertEqual(result.rate_date, date(2026, 9, 4))
        http_get.assert_called_once_with(
            "https://api.frankfurter.dev/v2/rate/EUR/USD",
            params={"providers": "ECB"},
            timeout=(3.05, 10),
        )

    def test_coingecko_latest_is_decimal_and_explicitly_delayed(self):
        http_get = Mock(
            return_value=response_with(
                {"bitcoin": {"usd": 12345.6789, "last_updated_at": 1788566400}}
            )
        )

        result = CoinGeckoProvider(http_get=http_get).latest("bitcoin", quote_currency="USD")

        self.assertEqual(result.close, Decimal("12345.6789"))
        self.assertEqual(result.currency, "USD")
        self.assertTrue(result.is_delayed)
        self.assertEqual(result.observed_at.tzinfo, UTC)

    def test_yahoo_adapter_maps_ohlcv_currency_and_market_metadata(self):
        index = pd.DatetimeIndex([datetime(2026, 9, 4, tzinfo=UTC)])
        frame = pd.DataFrame(
            {
                "Open": ["99.5"],
                "High": ["101"],
                "Low": ["98"],
                "Close": ["100.25"],
                "Volume": ["1200"],
            },
            index=index,
        )
        ticker = SimpleNamespace(
            history=Mock(return_value=frame),
            history_metadata={
                "currency": "EUR",
                "marketState": "CLOSED",
                "exchangeTimezoneName": "Europe/Paris",
            },
        )
        module = SimpleNamespace(Ticker=Mock(return_value=ticker))

        result = YahooFinanceProvider(module=module).latest("AC.PA")

        self.assertEqual(result.close, Decimal("100.25"))
        self.assertEqual(result.currency, "EUR")
        self.assertEqual(result.market_state, "CLOSED")
        self.assertTrue(result.is_delayed)


class FakeProvider:
    name = "yahoo"

    def __init__(self, quote=None, error=None):
        self.quote = quote
        self.error = error

    def latest(self, provider_id, *, quote_currency=None):
        if self.error:
            raise self.error
        return self.quote

    def history(self, provider_id, *, start, end, quote_currency=None):
        return []


class MarketDataPersistenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="market-user")
        cls.account = Account.objects.create(
            user=cls.user,
            name="CTO",
            category=Account.Type.CTO,
            balance=Decimal("100"),
            currency="EUR",
        )
        cls.instrument = Instrument.objects.create(
            owner=cls.user,
            name="Action test",
            instrument_type=Instrument.Type.STOCK,
            ticker="TEST.PA",
            currency="USD",
        )
        cls.position = Position.objects.create(
            account=cls.account,
            instrument=cls.instrument,
            quantity=Decimal("1.25"),
            current_value=Decimal("1"),
            value_currency="USD",
        )

    def setUp(self):
        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="EUR",
            rate=Decimal("0.8"),
            rate_date=date(2026, 9, 4),
            source="frankfurter-ecb",
        )

    def quote(self):
        observed_at = timezone.now()
        return MarketQuote(
            provider_id="TEST.PA",
            symbol="TEST.PA",
            close=Decimal("10"),
            currency="USD",
            observed_at=observed_at,
            collected_at=observed_at,
            source="yahoo",
            is_delayed=True,
            market_state="CLOSED",
            market_timezone="Europe/Paris",
        )

    def test_fx_refresh_stores_direct_inverse_and_is_idempotent(self):
        provider = Mock()
        provider.latest.return_value = FrankfurterProvider(
            http_get=Mock(
                return_value=response_with(
                    {"date": "2026-09-04", "base": "EUR", "quote": "USD", "rate": 1.25}
                )
            )
        ).latest("EUR", "USD")

        refresh_exchange_rate(provider=provider)
        refresh_exchange_rate(provider=provider)

        self.assertEqual(ExchangeRate.objects.count(), 2)
        self.assertEqual(get_stored_rate("EUR", "USD").rate, Decimal("1.25"))
        self.assertEqual(get_stored_rate("USD", "EUR").rate, Decimal("0.800000000000"))

    def test_price_refresh_is_idempotent_and_updates_owned_position(self):
        provider = FakeProvider(quote=self.quote())

        first = refresh_instrument_market_data(
            self.user,
            self.instrument,
            provider=provider,
            include_history=False,
        )
        second = refresh_instrument_market_data(
            self.user,
            self.instrument,
            provider=provider,
            include_history=False,
        )

        self.assertEqual(first[0].pk, second[0].pk)
        self.assertEqual(Price.objects.filter(instrument=self.instrument).count(), 1)
        self.position.refresh_from_db()
        self.assertEqual(self.position.current_value, Decimal("12.50000000"))
        self.assertEqual(self.position.converted_value, Decimal("10.00000000"))
        self.assertEqual(self.position.converted_currency, "EUR")
        status = MarketDataStatus.objects.get(user=self.user, instrument=self.instrument)
        self.assertEqual(status.state, MarketDataStatus.State.FRESH)

    def test_failed_refresh_keeps_last_good_price_and_records_error(self):
        refresh_instrument_market_data(
            self.user,
            self.instrument,
            provider=FakeProvider(quote=self.quote()),
            include_history=False,
        )

        with self.assertRaises(MarketDataError):
            refresh_instrument_market_data(
                self.user,
                self.instrument,
                provider=FakeProvider(error=MarketDataError("panne simulée")),
                include_history=False,
            )

        self.assertEqual(Price.objects.filter(instrument=self.instrument).count(), 1)
        status = MarketDataStatus.objects.get(user=self.user, instrument=self.instrument)
        self.assertEqual(status.state, MarketDataStatus.State.ERROR)
        self.assertIn("panne simulée", status.last_error)

    def test_failed_fx_refresh_keeps_the_last_stored_rate(self):
        provider = Mock()
        provider.latest.side_effect = MarketDataError("panne simulée")

        with self.assertRaises(MarketDataError):
            refresh_exchange_rate(provider=provider)

        stored = get_stored_rate("USD", "EUR")
        self.assertEqual(stored.rate, Decimal("0.8"))
        self.assertEqual(ExchangeRate.objects.count(), 1)

    def test_currency_display_defaults_equities_to_eur_and_can_show_usd(self):
        display = prepare_currency_display(Decimal("50"), "USD", "EUR")

        self.assertEqual(display.default_currency, "EUR")
        self.assertEqual(display.amount_eur, Decimal("40.00000000"))
        self.assertEqual(display.amount_usd, Decimal("50.00000000"))

    def test_daily_snapshots_are_complete_and_idempotent(self):
        self.position.delete()
        result = create_daily_snapshots(self.user, day=date(2026, 9, 5))
        repeated = create_daily_snapshots(self.user, day=date(2026, 9, 5))

        self.assertEqual(result.created, 2)
        self.assertEqual(repeated.existing, 2)
        self.assertEqual(Snapshot.objects.filter(user=self.user).count(), 2)
        net_worth = Snapshot.objects.get(user=self.user, scope=Snapshot.Scope.NET_WORTH)
        self.assertEqual(net_worth.converted_value, Decimal("100.00000000"))

    def test_incomplete_valuation_never_creates_a_partial_snapshot(self):
        ExchangeRate.objects.all().delete()

        with self.assertRaises(IncompleteValuationError):
            create_daily_snapshots(self.user, day=date(2026, 9, 5))

        self.assertFalse(Snapshot.objects.filter(user=self.user).exists())

    def test_mixed_manual_dates_and_market_datetimes_have_a_latest_observation(self):
        RealEstate.objects.create(
            user=self.user,
            manual_reference="home",
            name="Résidence",
            property_type=RealEstate.Type.APARTMENT,
            purchase_price=Decimal("100000"),
            estimated_value=Decimal("110000"),
            valuation_date=date(2026, 9, 1),
        )

        valuation = build_portfolio_valuation(self.user)

        self.assertIsNotNone(valuation.valued_at)

    def test_market_preferences_use_requested_defaults(self):
        preference = MarketDataPreference.objects.create(user=self.user)

        self.assertEqual(preference.equity_display_currency, "EUR")
        self.assertEqual(preference.crypto_display_currency, "USD")

    def test_coingecko_identifier_must_be_explicit(self):
        crypto = Instrument.objects.create(
            owner=self.user,
            name="Bitcoin",
            instrument_type=Instrument.Type.CRYPTO,
            ticker="BTC",
            currency="USD",
        )

        with self.assertRaisesRegex(MarketDataError, "Identifiant coingecko manquant"):
            provider_identifier(crypto, "coingecko")

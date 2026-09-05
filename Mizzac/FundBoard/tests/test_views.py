from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from FundBoard.models import (
    Account,
    ExchangeRate,
    Income,
    Instrument,
    MarketDataPreference,
    Position,
    Price,
    Subscription,
    Transaction,
)

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class FundBoardViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(username="alice")
        cls.bob = get_user_model().objects.create_user(username="bob")
        cls.alice_eur = Account.objects.create(
            user=cls.alice,
            name="Compte EUR",
            category="CURRENT",
            balance=Decimal("100.00"),
            currency="EUR",
        )
        cls.alice_usd = Account.objects.create(
            user=cls.alice,
            name="Compte USD",
            category="CTO",
            balance=Decimal("50.00"),
            currency="USD",
        )
        cls.bob_account = Account.objects.create(
            user=cls.bob,
            name="Compte privé de Bob",
            category="CTO",
            balance=Decimal("999.00"),
            currency="EUR",
        )
        cls.alice_subscription = Subscription.objects.create(
            user=cls.alice,
            name="Mensuel Alice",
            amount=Decimal("12.50"),
            freq="MONTHLY",
            next_due=date(2026, 9, 30),
        )
        cls.alice_custom_subscription = Subscription.objects.create(
            user=cls.alice,
            name="Personnalisé Alice",
            amount=Decimal("3.50"),
            freq="PERSONALIZED",
            freq_custom=7,
            next_due=date(2026, 9, 10),
        )
        cls.bob_subscription = Subscription.objects.create(
            user=cls.bob,
            name="Abonnement privé de Bob",
            amount=Decimal("99.00"),
            freq="MONTHLY",
            next_due=date(2026, 9, 30),
        )
        cls.alice_income = Income.objects.create(
            user=cls.alice,
            name="Salaire Alice",
            amount=Decimal("1000.00"),
            freq="MONTHLY",
            next_payday=date(2026, 9, 30),
        )
        cls.bob_income = Income.objects.create(
            user=cls.bob,
            name="Revenu privé de Bob",
            amount=Decimal("2000.00"),
            freq="MONTHLY",
            next_payday=date(2026, 9, 30),
        )
        cls.alice_transaction = Transaction.objects.create(
            user=cls.alice,
            account=cls.alice_eur,
            net_amount=Decimal("25.00"),
            currency="EUR",
            transaction_type="DEPOSIT",
        )
        cls.bob_transaction = Transaction.objects.create(
            user=cls.bob,
            account=cls.bob_account,
            net_amount=Decimal("500.00"),
            currency="EUR",
            transaction_type="DEPOSIT",
        )
        cls.alice_instrument = Instrument.objects.create(
            name="ETF public Alice",
            instrument_type=Instrument.Type.ETF,
            ticker="ALICE",
            currency="USD",
        )
        cls.bob_instrument = Instrument.objects.create(
            name="Instrument privé de Bob",
            instrument_type=Instrument.Type.STOCK,
            ticker="BOB",
            currency="EUR",
        )
        Position.objects.create(
            account=cls.alice_usd,
            instrument=cls.alice_instrument,
            quantity=Decimal("1.25"),
            current_value=Decimal("50"),
            value_currency="USD",
        )
        Position.objects.create(
            account=cls.bob_account,
            instrument=cls.bob_instrument,
            quantity=Decimal("999"),
            current_value=Decimal("999"),
            value_currency="EUR",
        )

    def setUp(self):
        self.client.force_login(self.alice)

    def test_primary_fundboard_pages_render(self):
        route_names = [
            "fundboard:fundboard",
            "fundboard:portfolio",
            "fundboard:transactions",
            "fundboard:subscriptions",
            "fundboard:revenues",
            "fundboard:accounts",
            "fundboard:market_settings",
        ]

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_dashboard_refuses_to_add_currencies_without_a_rate(self):
        response = self.client.get(reverse("fundboard:fundboard"))

        self.assertContains(response, "100,00 EUR")
        self.assertContains(response, "Valorisation partielle")
        self.assertNotContains(response, "150,00 EUR")

    def test_dashboard_uses_a_dated_rate_for_consolidation(self):
        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="EUR",
            rate=Decimal("0.8"),
            rate_date=date(2026, 9, 5),
            source="frankfurter-ecb",
        )

        response = self.client.get(reverse("fundboard:fundboard"))

        self.assertEqual(response.context["valuation"].net_worth, Decimal("180.00000000"))
        self.assertTrue(response.context["valuation"].complete)

    def test_lists_do_not_expose_another_users_data(self):
        expectations = [
            ("fundboard:accounts", "Compte EUR", "Compte privé de Bob"),
            ("fundboard:transactions", "25,00", "500,00"),
            ("fundboard:subscriptions", "Mensuel Alice", "Abonnement privé de Bob"),
            ("fundboard:revenues", "Salaire Alice", "Revenu privé de Bob"),
            ("fundboard:portfolio", "ETF public Alice", "Instrument privé de Bob"),
        ]

        for route_name, own_value, other_value in expectations:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, own_value)
                self.assertNotContains(response, other_value)

    def test_subscription_chart_uses_safe_json_script(self):
        response = self.client.get(reverse("fundboard:subscriptions"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="subscription-chart-labels"', content)
        self.assertIn('id="subscription-chart-values"', content)
        self.assertIn('id="subscription-chart-currencies"', content)
        self.assertIn("MizzacCharts.mount", content)
        self.assertNotIn("Decimal(", content)
        self.assertNotIn("|safe", content)

    def test_subscription_chart_keeps_currencies_separate(self):
        Subscription.objects.create(
            user=self.alice,
            name="Mensuel USD",
            amount=Decimal("7.00"),
            currency="USD",
            freq="MONTHLY",
            next_due=date(2026, 9, 30),
        )

        response = self.client.get(reverse("fundboard:subscriptions"))

        self.assertEqual(
            response.context["chart_labels"],
            ["Mensuel · EUR", "Personnalisé · EUR", "Mensuel · USD"],
        )
        self.assertEqual(response.context["chart_values"], ["12.5", "3.5", "7"])
        self.assertEqual(response.context["chart_currencies"], ["EUR", "EUR", "USD"])

    def test_detail_pages_enforce_ownership(self):
        own_urls = [
            reverse("fundboard:account_detail", args=[self.alice_eur.pk]),
            reverse("fundboard:instrument_detail", args=[self.alice_instrument.pk]),
        ]
        other_urls = [
            reverse("fundboard:account_detail", args=[self.bob_account.pk]),
            reverse("fundboard:instrument_detail", args=[self.bob_instrument.pk]),
        ]

        for url in own_urls:
            self.assertEqual(self.client.get(url).status_code, 200)
        for url in other_urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_instrument_detail_shows_source_time_market_state_and_delay(self):
        Price.objects.create(
            instrument=self.alice_instrument,
            observed_at=timezone.now(),
            close_price=Decimal("42.5"),
            currency="USD",
            source="yahoo",
            is_delayed=True,
            market_state=Price.MarketState.CLOSED,
            market_timezone="Europe/Paris",
        )

        response = self.client.get(
            reverse("fundboard:instrument_detail", args=[self.alice_instrument.pk])
        )

        self.assertContains(response, "yahoo")
        self.assertContains(response, "Marché fermé")
        self.assertContains(response, "Europe/Paris")
        self.assertContains(response, "Différé / non garanti")

    def test_portfolio_exposes_safe_eur_usd_toggle_data(self):
        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="EUR",
            rate=Decimal("0.8"),
            rate_date=date(2026, 9, 5),
            source="frankfurter-ecb",
        )

        response = self.client.get(reverse("fundboard:portfolio"))

        self.assertContains(response, 'data-currency-mode="DEFAULT"')
        self.assertContains(response, 'data-default-currency="EUR"')
        self.assertContains(response, 'data-amount-eur="40.00000000"')
        self.assertContains(response, 'data-amount-usd="50.00000000"')

    def test_crypto_defaults_to_usd_while_equities_default_to_eur(self):
        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="EUR",
            rate=Decimal("0.8"),
            rate_date=date(2026, 9, 5),
            source="frankfurter-ecb",
        )
        crypto_account = Account.objects.create(
            user=self.alice,
            name="Wallet",
            category=Account.Type.CRYPTO,
            currency="USD",
        )
        crypto = Instrument.objects.create(
            owner=self.alice,
            name="Bitcoin",
            instrument_type=Instrument.Type.CRYPTO,
            ticker="BTC",
            currency="USD",
            provider_identifiers={"coingecko": "bitcoin"},
        )
        Position.objects.create(
            account=crypto_account,
            instrument=crypto,
            quantity=Decimal("1"),
            current_value=Decimal("100"),
            value_currency="USD",
        )

        response = self.client.get(reverse("fundboard:portfolio"))

        self.assertContains(response, 'data-default-currency="EUR"')
        self.assertContains(response, 'data-default-currency="USD"')

    @patch("FundBoard.view_modules.market_data.refresh_instrument_market_data")
    @patch("FundBoard.view_modules.market_data.refresh_exchange_rate")
    def test_provider_and_snapshot_actions_are_post_only(self, refresh_fx, refresh_instrument):
        paths = [
            reverse("fundboard:refresh_fx"),
            reverse("fundboard:refresh_benchmark"),
            reverse("fundboard:create_snapshot"),
            reverse("fundboard:refresh_instrument", args=[self.alice_instrument.pk]),
        ]

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 405)
        refresh_fx.assert_not_called()
        refresh_instrument.assert_not_called()

    @patch("FundBoard.view_modules.market_data.refresh_exchange_rate")
    def test_market_refresh_requires_csrf(self, refresh_fx):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.alice)

        response = csrf_client.post(reverse("fundboard:refresh_fx"))

        self.assertEqual(response.status_code, 403)
        refresh_fx.assert_not_called()

    @patch("FundBoard.view_modules.market_data.refresh_instrument_market_data")
    def test_market_refresh_cannot_target_another_users_instrument(self, refresh):
        response = self.client.post(
            reverse("fundboard:refresh_instrument", args=[self.bob_instrument.pk])
        )

        self.assertEqual(response.status_code, 404)
        refresh.assert_not_called()

    def test_market_preferences_are_private_to_each_user(self):
        response = self.client.post(
            reverse("fundboard:market_settings"),
            {
                "reporting_currency": "USD",
                "equity_display_currency": "USD",
                "crypto_display_currency": "EUR",
                "benchmark_symbol": "^GSPC",
            },
        )

        self.assertRedirects(response, reverse("fundboard:market_settings"))
        alice_preference = MarketDataPreference.objects.get(user=self.alice)
        self.assertEqual(alice_preference.reporting_currency, "USD")
        self.assertEqual(alice_preference.benchmark_symbol, "^GSPC")
        self.assertFalse(MarketDataPreference.objects.filter(user=self.bob).exists())

    def test_anonymous_users_are_redirected_from_pages_and_modals(self):
        self.client.logout()
        routes = [
            reverse("fundboard:fundboard"),
            reverse("fundboard:market_settings"),
            reverse("fundboard:refresh_fx"),
            reverse("fundboard:refresh_benchmark"),
            reverse("fundboard:create_snapshot"),
            reverse("fundboard:instrument_detail", args=[self.alice_instrument.pk]),
            reverse("fundboard:refresh_instrument", args=[self.alice_instrument.pk]),
            reverse("fundboard:account_detail", args=[self.alice_eur.pk]),
            reverse("fundboard:account_source_modal"),
            reverse("fundboard:add_account_modal"),
            reverse("fundboard:edit_account_modal", args=[self.alice_eur.pk]),
            reverse("fundboard:delete_account_modal", args=[self.alice_eur.pk]),
            reverse("fundboard:add_subscription_modal"),
            reverse(
                "fundboard:edit_subscription_modal",
                args=[self.alice_subscription.pk],
            ),
            reverse(
                "fundboard:delete_subscription_modal",
                args=[self.alice_subscription.pk],
            ),
        ]

        for path in routes:
            with self.subTest(path=path):
                response = self.client.get(path, **AJAX)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("dashboard:login")))

    def test_modal_get_requires_ajax_for_authenticated_user(self):
        response = self.client.get(reverse("fundboard:add_account_modal"))

        self.assertEqual(response.status_code, 403)

    def test_account_and_subscription_modals_enforce_ownership(self):
        own_routes = [
            reverse("fundboard:edit_account_modal", args=[self.alice_eur.pk]),
            reverse("fundboard:delete_account_modal", args=[self.alice_eur.pk]),
            reverse(
                "fundboard:edit_subscription_modal",
                args=[self.alice_subscription.pk],
            ),
            reverse(
                "fundboard:delete_subscription_modal",
                args=[self.alice_subscription.pk],
            ),
        ]
        other_routes = [
            reverse("fundboard:edit_account_modal", args=[self.bob_account.pk]),
            reverse("fundboard:delete_account_modal", args=[self.bob_account.pk]),
            reverse(
                "fundboard:edit_subscription_modal",
                args=[self.bob_subscription.pk],
            ),
            reverse(
                "fundboard:delete_subscription_modal",
                args=[self.bob_subscription.pk],
            ),
        ]

        for path in own_routes:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, **AJAX).status_code, 200)
        for path in other_routes:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, **AJAX).status_code, 404)

    def test_modal_write_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.alice)

        response = csrf_client.post(
            reverse("fundboard:add_account_modal"),
            {
                "name": "Sans CSRF",
                "category": "CURRENT",
                "balance": "10.00",
                "currency": "EUR",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Account.objects.filter(name="Sans CSRF").exists())

    def test_manual_account_form_normalizes_currency(self):
        response = self.client.post(
            reverse("fundboard:add_account_modal"),
            {
                "name": "Nouveau compte",
                "category": "SAVINGS",
                "balance": "42.10",
                "currency": "eur",
            },
        )

        self.assertRedirects(response, reverse("fundboard:accounts"))
        account = Account.objects.get(user=self.alice, name="Nouveau compte")
        self.assertEqual(account.currency, "EUR")

    def test_manual_account_form_rejects_invalid_currency(self):
        response = self.client.post(
            reverse("fundboard:add_account_modal"),
            {
                "name": "Devise invalide",
                "category": "SAVINGS",
                "balance": "42.10",
                "currency": "EURO",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "code devise ISO")
        self.assertFalse(Account.objects.filter(name="Devise invalide").exists())

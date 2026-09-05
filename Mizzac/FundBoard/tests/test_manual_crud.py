from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from FundBoard.models import (
    Account,
    FinancialAuditEvent,
    Instrument,
    Loan,
    Position,
    RealEstate,
    Transaction,
)

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class ManualCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(username="manual-alice")
        cls.bob = get_user_model().objects.create_user(username="manual-bob")
        cls.alice_account = Account.objects.create(
            user=cls.alice,
            manual_reference="alice-cto",
            name="CTO Alice",
            category=Account.Type.CTO,
            currency="EUR",
        )
        cls.bob_account = Account.objects.create(
            user=cls.bob,
            manual_reference="bob-cto",
            name="CTO Bob privé",
            category=Account.Type.CTO,
            currency="EUR",
        )
        cls.alice_instrument = Instrument.objects.create(
            owner=cls.alice,
            manual_reference="alice-etf",
            name="ETF Alice",
            instrument_type=Instrument.Type.ETF,
            currency="EUR",
        )
        cls.bob_instrument = Instrument.objects.create(
            owner=cls.bob,
            manual_reference="bob-etf",
            name="ETF Bob privé",
            instrument_type=Instrument.Type.ETF,
            currency="EUR",
        )
        cls.alice_position = Position.objects.create(
            account=cls.alice_account,
            instrument=cls.alice_instrument,
            quantity=Decimal("2"),
            value_currency="EUR",
        )
        cls.bob_position = Position.objects.create(
            account=cls.bob_account,
            instrument=cls.bob_instrument,
            quantity=Decimal("3"),
            value_currency="EUR",
        )
        cls.alice_transaction = Transaction.objects.create(
            user=cls.alice,
            account=cls.alice_account,
            transaction_type=Transaction.Type.DEPOSIT,
            net_amount=Decimal("100"),
            currency="EUR",
        )
        cls.bob_transaction = Transaction.objects.create(
            user=cls.bob,
            account=cls.bob_account,
            transaction_type=Transaction.Type.DEPOSIT,
            net_amount=Decimal("100"),
            currency="EUR",
        )

    def setUp(self):
        self.client.force_login(self.alice)

    def test_phase_four_pages_render_without_other_users_data(self):
        expectations = [
            ("fundboard:instruments", "ETF Alice", "ETF Bob privé"),
            ("fundboard:portfolio", "ETF Alice", "ETF Bob privé"),
            ("fundboard:transactions", "CTO Alice", "CTO Bob privé"),
            ("fundboard:real_estate", "Immobilier", "CTO Bob privé"),
            ("fundboard:loans", "Prêts", "CTO Bob privé"),
            ("fundboard:import_export", "Importer", "CTO Bob privé"),
        ]

        for route_name, own_text, foreign_text in expectations:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, own_text)
                self.assertNotContains(response, foreign_text)

    def test_edit_archive_and_cancel_modals_enforce_ownership(self):
        own_and_foreign_routes = [
            ("fundboard:edit_instrument_modal", self.alice_instrument.pk, self.bob_instrument.pk),
            ("fundboard:archive_instrument_modal", self.alice_instrument.pk, self.bob_instrument.pk),
            ("fundboard:edit_position_modal", self.alice_position.pk, self.bob_position.pk),
            ("fundboard:archive_position_modal", self.alice_position.pk, self.bob_position.pk),
            ("fundboard:edit_transaction_modal", self.alice_transaction.pk, self.bob_transaction.pk),
            ("fundboard:cancel_transaction_modal", self.alice_transaction.pk, self.bob_transaction.pk),
        ]

        for route_name, own_pk, foreign_pk in own_and_foreign_routes:
            with self.subTest(route_name=route_name):
                self.assertEqual(
                    self.client.get(reverse(route_name, args=[own_pk]), **AJAX).status_code,
                    200,
                )
                self.assertEqual(
                    self.client.get(reverse(route_name, args=[foreign_pk]), **AJAX).status_code,
                    404,
                )

    def test_manual_instrument_is_owned_by_authenticated_user(self):
        response = self.client.post(
            reverse("fundboard:add_instrument_modal"),
            {
                "manual_reference": "new-fund",
                "name": "Nouveau fonds",
                "instrument_type": Instrument.Type.FUND,
                "currency": "eur",
                "status": Instrument.Status.ACTIVE,
            },
        )

        self.assertRedirects(response, reverse("fundboard:instruments"))
        instrument = Instrument.objects.get(manual_reference="new-fund")
        self.assertEqual(instrument.owner, self.alice)
        self.assertEqual(instrument.currency, "EUR")
        self.assertTrue(
            FinancialAuditEvent.objects.filter(
                user=self.alice,
                event_type=FinancialAuditEvent.Type.MANUAL_CREATE,
                object_type="Instrument",
                object_pk=instrument.pk,
            ).exists()
        )

    def test_archive_and_cancel_keep_records(self):
        self.client.post(
            reverse("fundboard:archive_position_modal", args=[self.alice_position.pk])
        )
        self.client.post(
            reverse("fundboard:cancel_transaction_modal", args=[self.alice_transaction.pk])
        )

        self.alice_position.refresh_from_db()
        self.alice_transaction.refresh_from_db()
        self.assertEqual(self.alice_position.status, Position.Status.ARCHIVED)
        self.assertEqual(self.alice_transaction.status, Transaction.Status.CANCELLED)


class LoanAndRealEstateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="property-user")
        cls.eur_loan = Loan.objects.create(
            user=cls.user,
            manual_reference="loan-eur",
            name="Prêt EUR",
            currency="EUR",
            original_principal=Decimal("200000"),
            outstanding_principal=Decimal("150000"),
            nominal_rate=Decimal("1.5"),
            duration_months=240,
            start_date=date(2022, 1, 1),
        )

    def test_owned_and_net_property_values_are_explicit(self):
        property_asset = RealEstate(
            user=self.user,
            linked_loan=self.eur_loan,
            manual_reference="home",
            name="Maison",
            property_type=RealEstate.Type.HOUSE,
            currency="EUR",
            purchase_price=Decimal("250000"),
            estimated_value=Decimal("300000"),
            ownership_share=Decimal("50"),
            valuation_date=date(2026, 9, 4),
        )

        self.assertEqual(property_asset.owned_value, Decimal("150000.00000000"))
        self.assertEqual(property_asset.net_value, Decimal("0E-8"))

    def test_net_value_requires_conversion_for_a_foreign_currency_loan(self):
        self.eur_loan.currency = "USD"
        property_asset = RealEstate(
            user=self.user,
            linked_loan=self.eur_loan,
            manual_reference="home-usd-loan",
            name="Maison",
            property_type=RealEstate.Type.HOUSE,
            currency="EUR",
            purchase_price=Decimal("250000"),
            estimated_value=Decimal("300000"),
            valuation_date=date(2026, 9, 4),
        )

        self.assertIsNone(property_asset.net_value)

    def test_loan_rejects_remaining_capital_above_initial_capital(self):
        invalid = Loan(
            user=self.user,
            manual_reference="invalid-loan",
            name="Invalide",
            currency="EUR",
            original_principal=Decimal("100"),
            outstanding_principal=Decimal("101"),
            nominal_rate=Decimal("1"),
            duration_months=12,
            start_date=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            invalid.full_clean()

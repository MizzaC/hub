from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.test import TestCase
from django.utils import timezone

from FundBoard.models import (
    Account,
    Connection,
    ExternalIdentifier,
    Income,
    Institution,
    Instrument,
    Position,
    Snapshot,
    Subscription,
    Transaction,
)


class OwnershipValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(username="alice")
        cls.bob = get_user_model().objects.create_user(username="bob")
        cls.alice_account = Account.objects.create(
            user=cls.alice,
            name="Alice EUR",
            category="CURRENT",
            balance=Decimal("100.00"),
            currency="EUR",
        )

    def test_transaction_accepts_matching_owner(self):
        transaction = Transaction(
            user=self.alice,
            account=self.alice_account,
            net_amount=Decimal("10.00"),
            currency="EUR",
            transaction_type="DEPOSIT",
        )

        transaction.full_clean()

    def test_transaction_rejects_account_owned_by_another_user(self):
        transaction = Transaction(
            user=self.bob,
            account=self.alice_account,
            net_amount=Decimal("10.00"),
            currency="EUR",
            transaction_type="DEPOSIT",
        )

        with self.assertRaises(ValidationError):
            transaction.full_clean()


class RecurringModelValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="recurring-user")

    def test_subscription_requires_positive_custom_frequency(self):
        subscription = Subscription(
            user=self.user,
            name="Incorrect",
            amount=Decimal("3.00"),
            freq="PERSONALIZED",
            freq_custom=-1,
            next_due=date(2026, 9, 30),
        )

        with self.assertRaises(ValidationError):
            subscription.full_clean()

    def test_income_rejects_custom_days_for_standard_frequency(self):
        income = Income(
            user=self.user,
            name="Salary",
            amount=Decimal("1000.00"),
            freq="MONTHLY",
            freq_custom=30,
            next_payday=date(2026, 9, 30),
        )

        with self.assertRaises(ValidationError):
            income.full_clean()


class CanonicalModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(username="canonical-alice")
        cls.bob = get_user_model().objects.create_user(username="canonical-bob")
        cls.institution = Institution.objects.create(
            name="Banque Exemple",
            slug="banque-exemple",
            country_code="FR",
        )
        cls.connection = Connection.objects.create(
            user=cls.alice,
            institution=cls.institution,
            provider="example",
            external_id="connection-alice",
            status=Connection.Status.ACTIVE,
        )
        cls.account = Account.objects.create(
            user=cls.alice,
            institution=cls.institution,
            connection=cls.connection,
            name="PEA Alice",
            category=Account.Type.PEA,
            currency="EUR",
            source=Account.Source.PROVIDER,
            external_id="account-alice",
        )
        cls.instrument = Instrument.objects.create(
            name="Fonds Monde",
            instrument_type=Instrument.Type.ETF,
            ticker="WORLD",
            isin="FR0000000001",
            currency="EUR",
        )

    def test_account_rejects_connection_from_another_user(self):
        bob_connection = Connection.objects.create(
            user=self.bob,
            provider="example",
            external_id="connection-bob",
        )
        account = Account(
            user=self.alice,
            connection=bob_connection,
            name="Invalide",
            category=Account.Type.CURRENT,
            currency="EUR",
        )

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_position_schema_supports_fractional_instrument_precision(self):
        quantity = Position._meta.get_field("quantity")
        unit_price = Position._meta.get_field("current_unit_price")

        self.assertEqual((quantity.max_digits, quantity.decimal_places), (36, 18))
        self.assertEqual((unit_price.max_digits, unit_price.decimal_places), (30, 12))

    def test_crypto_contract_requires_a_chain(self):
        instrument = Instrument(
            name="Token",
            instrument_type=Instrument.Type.CRYPTO,
            ticker="TKN",
            currency="EUR",
            contract_address="0x123",
        )

        with self.assertRaises(ValidationError):
            instrument.full_clean()

    def test_provider_transaction_requires_idempotency_key(self):
        imported = Transaction(
            user=self.alice,
            account=self.account,
            transaction_type=Transaction.Type.DEPOSIT,
            net_amount=Decimal("10"),
            currency="EUR",
            source=Transaction.Source.PROVIDER,
            provider="example",
            external_id="operation-1",
        )

        with self.assertRaises(ValidationError):
            imported.full_clean()

    def test_transaction_sign_convention_is_validated(self):
        purchase = Transaction(
            user=self.alice,
            account=self.account,
            transaction_type=Transaction.Type.BUY,
            net_amount=Decimal("10"),
            currency="EUR",
        )

        with self.assertRaises(ValidationError):
            purchase.full_clean()

    def test_transaction_idempotency_is_unique_per_user(self):
        values = {
            "user": self.alice,
            "account": self.account,
            "transaction_type": Transaction.Type.DEPOSIT,
            "net_amount": Decimal("10"),
            "currency": "EUR",
            "source": Transaction.Source.IMPORT,
            "idempotency_key": "import:sha256:row-1",
        }
        Transaction.objects.create(**values)

        with self.assertRaises(IntegrityError), db_transaction.atomic():
            Transaction.objects.create(**values)

    def test_provider_external_transaction_id_is_unique_per_user(self):
        values = {
            "user": self.alice,
            "account": self.account,
            "transaction_type": Transaction.Type.DEPOSIT,
            "net_amount": Decimal("10"),
            "currency": "EUR",
            "source": Transaction.Source.PROVIDER,
            "provider": "example",
            "external_id": "provider-operation-1",
        }
        Transaction.objects.create(**values, idempotency_key="sync:first")

        with self.assertRaises(IntegrityError), db_transaction.atomic():
            Transaction.objects.create(**values, idempotency_key="sync:second")

    def test_external_identifier_targets_exactly_one_object(self):
        identifier = ExternalIdentifier(
            user=self.alice,
            provider="example",
            external_id="ambiguous",
            account=self.account,
            instrument=self.instrument,
        )

        with self.assertRaises(ValidationError):
            identifier.full_clean()

    def test_external_identifier_rejects_another_users_account(self):
        bob_account = Account.objects.create(
            user=self.bob,
            name="Compte Bob",
            category=Account.Type.CURRENT,
            currency="EUR",
        )
        identifier = ExternalIdentifier(
            user=self.alice,
            provider="example",
            external_id="bob-account",
            account=bob_account,
        )

        with self.assertRaises(ValidationError):
            identifier.full_clean()

    def test_snapshot_scope_and_owner_are_validated(self):
        bob_account = Account.objects.create(
            user=self.bob,
            name="Épargne Bob",
            category=Account.Type.SAVINGS,
            currency="EUR",
        )
        snapshot = Snapshot(
            user=self.alice,
            scope=Snapshot.Scope.ACCOUNT,
            account=bob_account,
            observed_at=timezone.make_aware(datetime(2026, 9, 4, 12)),
            original_value=Decimal("100"),
            original_currency="EUR",
            converted_value=Decimal("100"),
            converted_currency="EUR",
            exchange_rate=Decimal("1"),
            exchange_rate_date=date(2026, 9, 4),
        )

        with self.assertRaises(ValidationError):
            snapshot.full_clean()

    def test_snapshot_rejects_inconsistent_converted_value(self):
        snapshot = Snapshot(
            user=self.alice,
            scope=Snapshot.Scope.NET_WORTH,
            observed_at=timezone.make_aware(datetime(2026, 9, 4, 12)),
            original_value=Decimal("100"),
            original_currency="USD",
            converted_value=Decimal("95"),
            converted_currency="EUR",
            exchange_rate=Decimal("0.90"),
            exchange_rate_date=date(2026, 9, 4),
        )

        with self.assertRaises(ValidationError):
            snapshot.full_clean()

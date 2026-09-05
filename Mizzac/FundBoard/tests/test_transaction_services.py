from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from FundBoard.models import Account, Transaction
from FundBoard.services.transactions import (
    IdempotencyConflict,
    link_internal_transfers,
    persist_idempotently,
)


class TransactionServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="transaction-service-user")
        cls.source_account = Account.objects.create(
            user=cls.user,
            name="Source",
            category=Account.Type.CURRENT,
            currency="EUR",
        )
        cls.target_account = Account.objects.create(
            user=cls.user,
            name="Cible",
            category=Account.Type.SAVINGS,
            currency="EUR",
        )

    def imported_candidate(self, *, amount=Decimal("25")):
        return Transaction(
            user=self.user,
            account=self.source_account,
            transaction_type=Transaction.Type.DEPOSIT,
            net_amount=amount,
            currency="EUR",
            source=Transaction.Source.IMPORT,
            idempotency_key="file:abc:row:1",
            executed_at=timezone.make_aware(datetime(2026, 9, 4, 10)),
            label="Virement reçu",
        )

    def test_exact_retry_returns_existing_transaction(self):
        first, first_created = persist_idempotently(self.imported_candidate())
        second, second_created = persist_idempotently(self.imported_candidate())

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_reused_key_with_different_payload_is_rejected(self):
        persist_idempotently(self.imported_candidate())

        with self.assertRaises(IdempotencyConflict):
            persist_idempotently(self.imported_candidate(amount=Decimal("30")))

    def test_internal_transfer_links_both_legs(self):
        outgoing = Transaction.objects.create(
            user=self.user,
            account=self.source_account,
            transaction_type=Transaction.Type.TRANSFER,
            net_amount=Decimal("-100"),
            currency="EUR",
        )
        incoming = Transaction.objects.create(
            user=self.user,
            account=self.target_account,
            transaction_type=Transaction.Type.TRANSFER,
            net_amount=Decimal("100"),
            currency="EUR",
        )

        link_internal_transfers(outgoing, incoming)
        outgoing.refresh_from_db()
        incoming.refresh_from_db()

        self.assertEqual(outgoing.linked_transfer, incoming)
        self.assertEqual(incoming.linked_transfer, outgoing)
        self.assertTrue(outgoing.is_internal_transfer)
        self.assertTrue(incoming.is_internal_transfer)

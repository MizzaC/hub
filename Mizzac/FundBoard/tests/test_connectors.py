import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from FundBoard.integrations.connectors.base import (
    ConnectionCheck,
    ConnectorError,
    RemoteAccount,
    RemoteInstrument,
    RemotePosition,
    RemoteTransaction,
    SyncPayload,
)
from FundBoard.integrations.connectors.binance import BinanceConnector
from FundBoard.integrations.connectors.enable_banking import EnableBankingConnector
from FundBoard.integrations.connectors.file_imports import TradeRepublicImportConnector
from FundBoard.models import Account, Connection, ConnectorSyncRun, Institution, Transaction
from FundBoard.services.connectors import (
    disconnect_connection,
    import_connection_file,
    sync_connection,
)


class JsonResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self.payload


class ConnectorAdapterTests(SimpleTestCase):
    @patch.dict(
        "os.environ",
        {"FUNDBOARD_BINANCE_API_KEY": "public-id", "FUNDBOARD_BINANCE_SECRET_KEY": "secret"},
    )
    def test_binance_uses_get_only_and_maps_decimal_values(self):
        session = Mock()
        session.get.side_effect = [
            JsonResponse({"serverTime": 1788595200000}),
            JsonResponse(
                {
                    "canTrade": False,
                    "canWithdraw": False,
                    "balances": [{"asset": "BTC", "free": "0.25", "locked": "0.01"}],
                }
            ),
            JsonResponse({"symbols": [{"baseAsset": "BTC", "quoteAsset": "USDT"}]}),
            JsonResponse(
                [
                    {
                        "id": 42,
                        "qty": "0.01",
                        "quoteQty": "600.10",
                        "price": "60010",
                        "commission": "0.10",
                        "commissionAsset": "USDT",
                        "isBuyer": True,
                        "time": 1788595200000,
                    }
                ]
            ),
        ]
        connector = BinanceConnector(
            session=session,
            clock=lambda: datetime(2026, 9, 5, tzinfo=timezone.utc),
            sleeper=lambda _: None,
        )
        connection = SimpleNamespace(
            provider="binance",
            secret_reference="env:binance",
            configuration={"symbols": ["BTCUSDT"], "initial_days": 30},
            display_name="Mon Binance",
            sync_cursor={},
        )

        payload = connector.sync(connection)

        self.assertEqual(payload.positions[0].quantity, Decimal("0.26"))
        self.assertEqual(payload.transactions[0].net_amount, Decimal("-600.20"))
        self.assertEqual(payload.transactions[0].currency, "USD")
        self.assertEqual(payload.transactions[0].metadata["settlement_asset"], "USDT")
        self.assertEqual(session.method_calls[0][0], "get")
        self.assertTrue(all(call[0] == "get" for call in session.method_calls))

    @patch.dict(
        "os.environ",
        {"FUNDBOARD_BINANCE_API_KEY": "public-id", "FUNDBOARD_BINANCE_SECRET_KEY": "secret"},
    )
    def test_binance_refuses_a_key_with_trade_permission(self):
        session = Mock()
        session.get.side_effect = [
            JsonResponse({"serverTime": 1788595200000}),
            JsonResponse({"canTrade": True, "canWithdraw": False}),
        ]
        connection = SimpleNamespace(
            provider="binance",
            secret_reference="env:binance",
            configuration={"symbols": ["BTCUSDT"], "initial_days": 30},
        )

        with self.assertRaisesMessage(ConnectorError, "trading et les retraits"):
            BinanceConnector(session=session, sleeper=lambda _: None).test_connection(connection)

    def test_binance_trade_history_paginates_with_from_id(self):
        first_page = [{"id": value} for value in range(2, 1002)]
        session = Mock()
        session.get.side_effect = [JsonResponse(first_page), JsonResponse([{"id": 1002}])]
        connector = BinanceConnector(
            session=session,
            clock=lambda: datetime(2026, 9, 5, tzinfo=timezone.utc),
            sleeper=lambda _: None,
        )

        result = connector._trade_pages(
            "BTCUSDT",
            previous_id=1,
            initial_days=90,
            secrets={"api_key": "id", "secret_key": "secret"},
        )

        self.assertEqual(len(result), 1001)
        self.assertEqual(session.get.call_args_list[1].kwargs["params"]["fromId"], 1002)

    def test_binance_retries_a_rate_limit_without_exposing_payload(self):
        session = Mock()
        session.get.side_effect = [
            JsonResponse({"message": "sensitive"}, status=429, headers={"Retry-After": "1"}),
            JsonResponse({"serverTime": 1788595200000}),
        ]
        sleeper = Mock()

        payload = BinanceConnector(session=session, sleeper=sleeper)._request("/api/v3/time")

        self.assertEqual(payload["serverTime"], 1788595200000)
        sleeper.assert_called_once_with(1)

    def test_enable_banking_authorization_is_personal_and_signed(self):
        session = Mock()
        session.request.return_value = JsonResponse(
            {"url": "https://bank.example/consent", "authorization_id": "auth-1"}
        )
        encoder = Mock(return_value="jwt-token")
        connector = EnableBankingConnector(
            session=session,
            jwt_encoder=encoder,
            key_loader=lambda _: "private-key",
            clock=lambda: datetime(2026, 9, 5, tzinfo=timezone.utc),
        )
        connection = SimpleNamespace(
            provider="enable_banking",
            secret_reference="env:enable_banking",
            configuration={"bank_name": "Test Bank", "country": "FR", "consent_days": 180},
        )

        with patch.dict(
            "os.environ",
            {
                "FUNDBOARD_ENABLE_BANKING_APPLICATION_ID": "app-id",
                "FUNDBOARD_ENABLE_BANKING_PRIVATE_KEY_PATH": "/keys/private.pem",
            },
        ):
            url, authorization_id = connector.start_authorization(
                connection,
                redirect_url="https://local.test/callback",
                state="random-state",
            )

        self.assertEqual((url, authorization_id), ("https://bank.example/consent", "auth-1"))
        request_body = session.request.call_args.kwargs["json"]
        self.assertEqual(request_body["psu_type"], "personal")
        self.assertEqual(request_body["aspsp"], {"name": "Test Bank", "country": "FR"})
        self.assertNotIn("password", json.dumps(request_body).lower())
        self.assertEqual(encoder.call_args.kwargs["headers"]["kid"], "app-id")

    def test_enable_banking_maps_accounts_and_paginates_transactions(self):
        session = Mock()
        session.request.side_effect = [
            JsonResponse({"valid_until": "2027-03-04T00:00:00Z"}),
            JsonResponse({"accounts": [{"uid": "account-1"}]}),
            JsonResponse(
                {
                    "name": "Compte principal",
                    "cash_account_type": "CACC",
                    "account_id": {"iban": "FR7612345678901234567890123"},
                }
            ),
            JsonResponse(
                {
                    "balances": [
                        {
                            "balance_type": "CLBD",
                            "balance_amount": {"amount": "123.45", "currency": "EUR"},
                        }
                    ]
                }
            ),
            JsonResponse(
                {
                    "transactions": [
                        {
                            "entry_reference": "entry-1",
                            "transaction_amount": {"amount": "12.30", "currency": "EUR"},
                            "booking_date": "2026-09-04",
                            "remittance_information": "Virement reçu",
                        }
                    ],
                    "continuation_key": "next-page",
                }
            ),
            JsonResponse({"transactions": [], "continuation_key": ""}),
        ]
        connector = EnableBankingConnector(
            session=session,
            jwt_encoder=Mock(return_value="jwt-token"),
            key_loader=lambda _: "private-key",
            clock=lambda: datetime(2026, 9, 5, tzinfo=timezone.utc),
        )
        connection = SimpleNamespace(
            provider="enable_banking",
            secret_reference="env:enable_banking",
            configuration={"bank_name": "Test Bank", "country": "FR", "consent_days": 180},
            external_id="session-1",
            sync_cursor={},
        )

        with patch.dict(
            "os.environ",
            {
                "FUNDBOARD_ENABLE_BANKING_APPLICATION_ID": "app-id",
                "FUNDBOARD_ENABLE_BANKING_PRIVATE_KEY_PATH": "/keys/private.pem",
            },
        ):
            payload = connector.sync(connection)

        self.assertEqual(payload.accounts[0].balance, Decimal("123.45"))
        self.assertEqual(payload.accounts[0].iban_masked, "FR76 •••• 0123")
        self.assertEqual(payload.transactions[0].external_id, "bank:account-1:entry-1")
        transaction_calls = [
            call
            for call in session.request.call_args_list
            if "/transactions" in call.args[1]
        ]
        self.assertEqual(len(transaction_calls), 2)
        self.assertEqual(transaction_calls[1].kwargs["params"]["continuation_key"], "next-page")
        self.assertEqual(payload.cursor, {"accounts": {"account-1": "2026-09-05"}})

    def test_trade_republic_psd2_rejects_transaction_without_stable_id(self):
        with self.assertRaisesRegex(ValueError, "identifiant bancaire stable absent"):
            EnableBankingConnector._transaction(
                {
                    "transaction_amount": {"amount": "12.30", "currency": "EUR"},
                    "booking_date": "2026-09-04",
                },
                "trade-republic-account",
                require_stable_id=True,
            )

    def test_trade_republic_invalid_line_is_not_returned(self):
        content = json.dumps(
            [
                {"id": "ok-1", "timestamp": "2026-09-05", "title": "Dividende", "amount": {"value": "12.50", "currency": "EUR"}},
                {"id": "bad-1", "timestamp": "not-a-date", "amount": {"value": "5", "currency": "EUR"}},
            ]
        ).encode()
        connector = TradeRepublicImportConnector()

        payload = connector.parse(content, "trade-republic.json")

        self.assertEqual(len(payload.transactions), 1)
        self.assertEqual(payload.transactions[0].transaction_type, "DIVIDEND")
        self.assertEqual(len(payload.issues), 1)


class FakeConnector:
    import_only = False

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.revoked = False

    def sync(self, connection):
        if self.error:
            raise self.error
        return self.payload

    def test_connection(self, connection):
        return ConnectionCheck(("accounts",))

    def revoke(self, connection):
        self.revoked = True


class ConnectorPersistenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="connector-user")
        cls.institution = Institution.objects.create(
            name="Provider Test",
            slug="provider-test",
            institution_type=Institution.Type.BROKER,
        )

    def setUp(self):
        self.connection = Connection.objects.create(
            user=self.user,
            institution=self.institution,
            provider="test_provider",
            display_name="Source test",
            secret_reference="env:test_provider",
        )

    def payload(self):
        happened_at = datetime(2026, 9, 5, 8, tzinfo=timezone.utc)
        return SyncPayload(
            accounts=(RemoteAccount("acc-1", "Compte source", "CTO", "EUR", Decimal("10")),),
            instruments=(RemoteInstrument("asset-1", "Actif", "ACT", "STOCK", "EUR"),),
            positions=(RemotePosition("acc-1", "asset-1", Decimal("2"), "EUR"),),
            transactions=(
                RemoteTransaction(
                    "trx-1",
                    "acc-1",
                    "BUY",
                    Decimal("-10"),
                    "EUR",
                    happened_at,
                    instrument_external_id="asset-1",
                ),
            ),
            cursor={"page": 2},
        )

    def test_sync_is_idempotent_and_updates_cursor(self):
        first = sync_connection(self.connection, connector=FakeConnector(self.payload()))
        second = sync_connection(self.connection, connector=FakeConnector(self.payload()))

        self.assertEqual(first.status, ConnectorSyncRun.Status.SUCCEEDED)
        self.assertEqual(second.created_count, 0)
        self.assertEqual(second.skipped_count, 4)
        self.assertEqual(Account.objects.filter(connection=self.connection).count(), 1)
        self.assertEqual(Transaction.objects.filter(provider="test_provider").count(), 1)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.sync_cursor, {"page": 2})

    def test_invalid_item_is_rejected_without_blocking_valid_items(self):
        valid = self.payload().accounts[0]
        invalid = RemoteAccount("bad", "Compte invalide", "UNKNOWN", "EUR", Decimal("2"))
        payload = SyncPayload(accounts=(valid, invalid))

        run = sync_connection(self.connection, connector=FakeConnector(payload))

        self.assertEqual(run.status, ConnectorSyncRun.Status.PARTIAL)
        self.assertEqual(run.created_count, 1)
        self.assertEqual(run.rejected_count, 1)
        self.assertFalse(Account.objects.filter(connection=self.connection, external_id="bad").exists())

    def test_parallel_run_is_refused_before_provider_call(self):
        ConnectorSyncRun.objects.create(connection=self.connection)
        provider = Mock()

        with self.assertRaisesMessage(ConnectorError, "déjà en cours"):
            sync_connection(self.connection, connector=provider)

        provider.sync.assert_not_called()

    def test_provider_failure_is_redacted_and_traced(self):
        secret = "super-secret-value"
        error = ConnectorError("provider_rejected", "Le fournisseur a refusé la requête.")

        with self.assertRaises(ConnectorError):
            sync_connection(self.connection, connector=FakeConnector(error=error))

        run = self.connection.sync_runs.get()
        self.connection.refresh_from_db()
        self.assertEqual(run.status, ConnectorSyncRun.Status.FAILED)
        self.assertNotIn(secret, run.public_message)
        self.assertEqual(self.connection.last_error, "Le fournisseur a refusé la requête.")

    def test_disconnect_preserves_local_history_and_clears_access(self):
        sync_connection(self.connection, connector=FakeConnector(self.payload()))
        provider = FakeConnector()

        disconnect_connection(self.connection, connector=provider)

        self.connection.refresh_from_db()
        self.assertTrue(provider.revoked)
        self.assertEqual(self.connection.status, Connection.Status.REVOKED)
        self.assertEqual(self.connection.secret_reference, "")
        self.assertTrue(Account.objects.filter(connection=self.connection).exists())
        self.assertTrue(Transaction.objects.filter(provider="test_provider").exists())

    def test_file_import_marks_invalid_rows_partial(self):
        connection = Connection.objects.create(
            user=self.user,
            institution=self.institution,
            provider="trade_republic",
            display_name="TR import",
            configuration={"experimental_accepted": True},
        )
        content = json.dumps(
            [
                {"id": "valid", "timestamp": "2026-09-05", "amount": {"value": "10", "currency": "EUR"}},
                {"id": "invalid", "timestamp": "bad", "amount": {"value": "10", "currency": "EUR"}},
            ]
        ).encode()

        run = import_connection_file(connection, content, "tr.json")

        self.assertEqual(run.status, ConnectorSyncRun.Status.PARTIAL)
        self.assertEqual(run.rejected_count, 1)
        self.assertEqual(Transaction.objects.filter(provider="trade_republic").count(), 1)


class ConnectorViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(username="connector-alice")
        cls.bob = get_user_model().objects.create_user(username="connector-bob")
        institution = Institution.objects.create(name="Binance", slug="binance-test")
        cls.alice_connection = Connection.objects.create(
            user=cls.alice,
            institution=institution,
            provider="binance",
            display_name="Binance Alice",
            configuration={"symbols": ["BTCUSDT"], "initial_days": 90},
            secret_reference="env:binance",
        )
        cls.bob_connection = Connection.objects.create(
            user=cls.bob,
            institution=institution,
            provider="binance",
            display_name="Binance Bob",
            configuration={"symbols": ["BTCUSDT"], "initial_days": 90},
            secret_reference="env:binance",
        )

    def setUp(self):
        self.client.force_login(self.alice)

    def test_get_pages_never_call_a_provider(self):
        with patch("requests.sessions.Session.request", side_effect=AssertionError("network")), patch(
            "requests.sessions.Session.get", side_effect=AssertionError("network")
        ):
            list_response = self.client.get(reverse("fundboard:connections"))
            detail_response = self.client.get(
                reverse("fundboard:connection_detail", args=[self.alice_connection.pk])
            )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(list_response, "Binance Bob")

    def test_create_connection_stores_only_an_environment_reference(self):
        response = self.client.post(
            reverse("fundboard:connections"),
            {
                "provider": "enable_banking",
                "display_name": "Ma banque",
                "bank_name": "Test Bank",
                "country": "FR",
                "consent_days": "180",
            },
        )

        connection = Connection.objects.get(user=self.alice, display_name="Ma banque")
        self.assertRedirects(
            response,
            reverse("fundboard:connection_detail", args=[connection.pk]),
        )
        self.assertEqual(connection.secret_reference, "env:enable_banking")
        self.assertEqual(connection.configuration["bank_name"], "Test Bank")

    def test_trade_republic_psd2_creates_an_enable_banking_connection(self):
        response = self.client.post(
            reverse("fundboard:connections"),
            {
                "provider": "trade_republic_psd2",
                "display_name": "Trade Republic automatique",
            },
        )

        connection = Connection.objects.get(
            user=self.alice,
            display_name="Trade Republic automatique",
        )
        self.assertRedirects(
            response,
            reverse("fundboard:connection_detail", args=[connection.pk]),
        )
        self.assertEqual(connection.provider, "enable_banking")
        self.assertEqual(connection.configuration["bank_name"], "Trade Republic")
        self.assertEqual(connection.configuration["country"], "DE")
        self.assertTrue(connection.configuration["trade_republic_cash_only"])
        self.assertTrue(connection.configuration["requires_stable_transaction_id"])

    @patch("FundBoard.view_modules.connectors.test_connection")
    def test_test_button_calls_service_only_on_post(self, service):
        response = self.client.post(
            reverse("fundboard:connection_test", args=[self.alice_connection.pk])
        )

        self.assertRedirects(
            response,
            reverse("fundboard:connection_detail", args=[self.alice_connection.pk]),
        )
        service.assert_called_once()

    @patch("FundBoard.view_modules.connectors.sync_connection")
    def test_sync_button_reports_redacted_counters(self, service):
        service.return_value = SimpleNamespace(
            created_count=2,
            updated_count=1,
            rejected_count=1,
        )

        response = self.client.post(
            reverse("fundboard:connection_sync", args=[self.alice_connection.pk]),
            follow=True,
        )

        self.assertContains(response, "2 créé(s), 1 mis à jour, 1 ignoré(s)")
        service.assert_called_once()

    @patch("FundBoard.view_modules.connectors.disconnect_connection")
    def test_disconnect_button_keeps_provider_details_out_of_message(self, service):
        response = self.client.post(
            reverse("fundboard:connection_disconnect", args=[self.alice_connection.pk]),
            follow=True,
        )

        self.assertContains(response, "historique conservé")
        service.assert_called_once()

    def test_actions_enforce_ownership(self):
        response = self.client.post(
            reverse("fundboard:connection_sync", args=[self.bob_connection.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_mutating_action_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        response = client.post(
            reverse("fundboard:connection_disconnect", args=[self.alice_connection.pk])
        )
        self.assertEqual(response.status_code, 403)

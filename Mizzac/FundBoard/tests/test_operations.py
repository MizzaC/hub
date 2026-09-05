import io
import json
import logging
import sqlite3
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from Core.observability import JsonLogFormatter, SecretRedactionFilter
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from FundBoard.integrations.connectors.base import ConnectorError
from FundBoard.models import (
    Connection,
    ConnectorSyncRun,
    Instrument,
    MaintenanceRun,
    Price,
    VirtualOrder,
    VirtualPortfolio,
)
from FundBoard.services.backups import (
    BackupError,
    create_sqlite_backup,
    manifest_path,
    restore_sqlite_backup,
    verify_database_backup,
)
from FundBoard.services.health import operational_health
from FundBoard.services.maintenance import (
    MaintenanceAlreadyRunning,
    run_user_maintenance,
)
from FundBoard.services.paper_trading import (
    add_to_virtual_watchlist,
    initialize_virtual_portfolio,
    place_virtual_order,
)


class MaintenanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="maintenance-user",
            password="test-password",
        )
        cls.other = get_user_model().objects.create_user(username="maintenance-other")
        cls.stock = Instrument.objects.create(
            name="Maintenance Stock",
            instrument_type=Instrument.Type.STOCK,
            ticker="MAINT",
            currency="EUR",
        )

    def portfolio_with_open_order(self):
        portfolio = VirtualPortfolio.objects.create(
            user=self.user,
            name="Automatique",
            base_currency="EUR",
            initial_cash=Decimal("1000"),
            cash_balance=Decimal("1000"),
        )
        initialize_virtual_portfolio(portfolio)
        add_to_virtual_watchlist(portfolio, self.stock)
        order = place_virtual_order(
            portfolio,
            self.stock,
            side=VirtualOrder.Side.BUY,
            order_type=VirtualOrder.OrderType.LIMIT,
            quantity=Decimal("1"),
            limit_price=Decimal("90"),
        )
        self.assertEqual(order.status, VirtualOrder.Status.OPEN)
        return portfolio, order

    def test_local_maintenance_is_idempotent_and_executes_from_local_price_only(self):
        portfolio, order = self.portfolio_with_open_order()
        now = timezone.now()
        Price.objects.create(
            instrument=self.stock,
            observed_at=now - timedelta(minutes=1),
            close_price=Decimal("80"),
            currency="EUR",
            source="maintenance-test",
            market_state=Price.MarketState.REGULAR,
        )

        with patch("requests.sessions.Session.request") as network_call:
            first = run_user_maintenance(self.user, as_of=now)
            second = run_user_maintenance(self.user, as_of=now + timedelta(minutes=1))

        order.refresh_from_db()
        self.assertEqual(first.status, MaintenanceRun.Status.SUCCEEDED)
        self.assertEqual(first.virtual_order_executed_count, 1)
        self.assertEqual(first.connector_run_count, 0)
        self.assertEqual(second.virtual_order_executed_count, 0)
        self.assertGreaterEqual(second.snapshot_existing_count, 1)
        self.assertEqual(order.status, VirtualOrder.Status.EXECUTED)
        self.assertEqual(portfolio.performance_snapshots.count(), 1)
        network_call.assert_not_called()

    def test_network_sync_requires_opt_in_and_respects_due_date(self):
        now = timezone.now()
        due = Connection.objects.create(
            user=self.user,
            provider="binance",
            display_name="Due",
            status=Connection.Status.ACTIVE,
            next_sync_at=now - timedelta(minutes=1),
        )
        Connection.objects.create(
            user=self.user,
            provider="binance",
            display_name="Later",
            status=Connection.Status.ACTIVE,
            next_sync_at=now + timedelta(hours=1),
        )
        connector = SimpleNamespace(import_only=False)
        sync_result = SimpleNamespace(status=ConnectorSyncRun.Status.SUCCEEDED)

        with (
            patch("FundBoard.services.maintenance.get_connector", return_value=connector),
            patch("FundBoard.services.maintenance.refresh_exchange_rate"),
            patch(
                "FundBoard.services.maintenance.sync_connection",
                return_value=sync_result,
            ) as sync,
        ):
            local = run_user_maintenance(self.user, as_of=now)
            network = run_user_maintenance(
                self.user,
                include_network=True,
                as_of=now,
            )

        self.assertEqual(local.connector_run_count, 0)
        self.assertEqual(network.connector_run_count, 1)
        self.assertEqual(sync.call_args.args[0].pk, due.pk)
        due.refresh_from_db()
        self.assertEqual(due.next_sync_at, now + timedelta(hours=6))

    def test_connector_failure_is_partial_and_schedules_retry(self):
        now = timezone.now()
        due = Connection.objects.create(
            user=self.user,
            provider="binance",
            display_name="Failure",
            status=Connection.Status.ACTIVE,
            next_sync_at=now,
        )
        connector = SimpleNamespace(import_only=False)
        error = ConnectorError("offline", "Fournisseur indisponible.")
        with (
            patch("FundBoard.services.maintenance.get_connector", return_value=connector),
            patch("FundBoard.services.maintenance.refresh_exchange_rate"),
            patch("FundBoard.services.maintenance.sync_connection", side_effect=error),
        ):
            run = run_user_maintenance(self.user, include_network=True, as_of=now)

        due.refresh_from_db()
        self.assertEqual(run.status, MaintenanceRun.Status.PARTIAL)
        self.assertEqual(run.connector_failure_count, 1)
        self.assertEqual(due.next_sync_at, now + timedelta(minutes=30))
        self.assertNotIn("offline", json.dumps(run.details))

    def test_network_opt_in_refreshes_only_tracked_market_instruments(self):
        self.portfolio_with_open_order()
        with (
            patch("FundBoard.services.maintenance.refresh_exchange_rate") as refresh_fx,
            patch(
                "FundBoard.services.maintenance.refresh_instrument_market_data"
            ) as refresh_market,
        ):
            run = run_user_maintenance(self.user, include_network=True)

        refresh_fx.assert_called_once_with()
        self.assertEqual(refresh_market.call_args.args[:2], (self.user, self.stock))
        self.assertFalse(refresh_market.call_args.kwargs["include_history"])
        self.assertEqual(run.market_refresh_count, 1)
        self.assertEqual(run.market_failure_count, 0)
        self.assertTrue(run.fx_refresh_succeeded)

    def test_running_lock_and_stale_run_recovery(self):
        running = MaintenanceRun.objects.create(user=self.user)
        with self.assertRaises(MaintenanceAlreadyRunning):
            run_user_maintenance(self.user)

        MaintenanceRun.objects.filter(pk=running.pk).update(
            started_at=timezone.now() - timedelta(hours=3)
        )
        replacement = run_user_maintenance(self.user)
        running.refresh_from_db()

        self.assertEqual(running.status, MaintenanceRun.Status.FAILED)
        self.assertEqual(replacement.status, MaintenanceRun.Status.SUCCEEDED)

    def test_unexpected_failure_is_recorded_without_exception_details(self):
        with (
            patch(
                "FundBoard.services.maintenance.create_daily_snapshots",
                side_effect=RuntimeError("password=do-not-log"),
            ),
            self.assertRaises(RuntimeError),
        ):
            run_user_maintenance(self.user)

        run = MaintenanceRun.objects.get(user=self.user)
        self.assertEqual(run.status, MaintenanceRun.Status.FAILED)
        self.assertEqual(run.details, {"error_code": "internal_error"})
        self.assertNotIn("do-not-log", run.public_message)

    def test_management_command_rejects_force_without_network(self):
        with self.assertRaises(CommandError):
            call_command(
                "run_fundboard_maintenance",
                username=self.user.username,
                force_network=True,
            )


class BackupTests(TestCase):
    def make_source(self, directory):
        source = Path(directory) / "source.sqlite3"
        database = sqlite3.connect(source)
        database.executescript(
            "CREATE TABLE django_migrations "
            "(id INTEGER PRIMARY KEY, app TEXT, name TEXT, applied TEXT);"
            "INSERT INTO django_migrations(app, name, applied) "
            "VALUES ('FundBoard', '0008_test', '2026-09-05');"
            "CREATE TABLE FundBoard_sample (id INTEGER PRIMARY KEY, value TEXT);"
            "INSERT INTO FundBoard_sample(value) VALUES ('privé');"
        )
        database.commit()
        database.close()
        return source

    def test_sqlite_backup_verification_and_restore_to_new_file(self):
        with TemporaryDirectory() as directory:
            source = self.make_source(directory)
            backup = create_sqlite_backup(source, directory, label="test backup")
            verification = verify_database_backup(backup)
            destination = Path(directory) / "restored.sqlite3"
            restored = restore_sqlite_backup(backup, destination)

            self.assertEqual(verification.engine, "sqlite")
            self.assertEqual(verification.integrity, "ok")
            self.assertEqual(verification.migration_count, 1)
            self.assertTrue(manifest_path(backup).exists())
            database = sqlite3.connect(restored)
            self.assertEqual(
                database.execute("SELECT value FROM FundBoard_sample").fetchone()[0],
                "privé",
            )
            database.close()

            with self.assertRaisesRegex(BackupError, "existe déjà"):
                restore_sqlite_backup(backup, destination)

    def test_tampered_backup_is_rejected(self):
        with TemporaryDirectory() as directory:
            source = self.make_source(directory)
            backup = create_sqlite_backup(source, directory)
            with backup.open("ab") as stream:
                stream.write(b"tampered")

            with self.assertRaisesRegex(BackupError, "empreinte"):
                verify_database_backup(backup)

    def test_verify_command_outputs_only_operational_metadata(self):
        with TemporaryDirectory() as directory:
            source = self.make_source(directory)
            backup = create_sqlite_backup(source, directory)
            output = io.StringIO()

            call_command("verify_fundboard_backup", backup=str(backup), stdout=output)

            self.assertIn("SHA-256", output.getvalue())
            self.assertNotIn("privé", output.getvalue())


class HealthAndOperationsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="operations-user",
            password="test-password",
        )
        cls.other = get_user_model().objects.create_user(username="operations-other")

    def setUp(self):
        self.client.force_login(self.user)

    def test_health_detects_attention_and_stale_runs_per_user(self):
        now = timezone.now()
        Connection.objects.create(
            user=self.user,
            provider="binance",
            display_name="Erreur",
            status=Connection.Status.ERROR,
            next_sync_at=now - timedelta(minutes=1),
        )
        stale = MaintenanceRun.objects.create(user=self.user)
        MaintenanceRun.objects.filter(pk=stale.pk).update(
            started_at=now - timedelta(hours=3)
        )

        result = operational_health(user=self.user, as_of=now)
        other = operational_health(user=self.other, as_of=now)

        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.stale_maintenance_count, 1)
        self.assertEqual(result.connection_attention_count, 1)
        self.assertEqual(result.overdue_connection_count, 1)
        self.assertEqual(other.status, "OK")

    def test_operations_page_is_private_and_local_button_never_uses_network(self):
        MaintenanceRun.objects.create(
            user=self.other,
            status=MaintenanceRun.Status.SUCCEEDED,
            public_message="OTHER-PRIVATE",
        )
        response = self.client.get(reverse("fundboard:operations"))
        self.assertContains(response, "Exploitation")
        self.assertNotContains(response, "OTHER-PRIVATE")

        with patch("requests.sessions.Session.request") as network_call:
            trigger = self.client.post(reverse("fundboard:run_local_maintenance"))

        self.assertRedirects(trigger, reverse("fundboard:operations"))
        self.assertTrue(
            MaintenanceRun.objects.filter(user=self.user, include_network=False).exists()
        )
        network_call.assert_not_called()

    def test_operations_log_query_count_does_not_grow_with_rows(self):
        with CaptureQueriesContext(connection) as baseline_queries:
            self.client.get(reverse("fundboard:operations"))
        for index in range(10):
            MaintenanceRun.objects.create(
                user=self.user,
                status=MaintenanceRun.Status.SUCCEEDED,
                public_message=f"run-{index}",
            )
        with CaptureQueriesContext(connection) as populated_queries:
            response = self.client.get(reverse("fundboard:operations"))

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(populated_queries), len(baseline_queries) + 1)


class SecurityAndLoggingTests(TestCase):
    def test_secret_filter_and_json_formatter_never_emit_values(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.addFilter(SecretRedactionFilter())
        handler.setFormatter(JsonLogFormatter())
        logger = logging.getLogger("FundBoard.test.redaction")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        logger.info("token=abc123 Authorization: Bearer def456 password=hunter2")
        payload = json.loads(output.getvalue())

        self.assertNotIn("abc123", payload["message"])
        self.assertNotIn("def456", payload["message"])
        self.assertNotIn("hunter2", payload["message"])
        self.assertIn("[REDACTED]", payload["message"])

    def test_shared_security_headers_are_present(self):
        user = get_user_model().objects.create_user(username="security-user")
        self.client.force_login(user)

        response = self.client.get(reverse("fundboard:operations"))

        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertIn("camera=()", response["Permissions-Policy"])

"""Scheduled FundBoard maintenance with explicit network opt-in."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from FundBoard.integrations.connectors import get_connector
from FundBoard.integrations.connectors.base import ConnectorError
from FundBoard.models import (
    Connection,
    ConnectorSyncRun,
    Instrument,
    MaintenanceRun,
    VirtualOrder,
    VirtualPortfolio,
)

from .connectors import sync_connection
from .fx import refresh_exchange_rate
from .paper_trading import create_virtual_snapshot, process_open_virtual_orders
from .pricing import refresh_instrument_market_data
from .snapshots import IncompleteValuationError, create_daily_snapshots

logger = logging.getLogger(__name__)


class MaintenanceAlreadyRunning(RuntimeError):
    pass


@dataclass
class MaintenanceCounters:
    snapshot_created: int = 0
    snapshot_existing: int = 0
    virtual_portfolios: int = 0
    virtual_orders_executed: int = 0
    virtual_orders_rejected: int = 0
    market_refreshes: int = 0
    market_failures: int = 0
    fx_refreshed: bool = False
    connector_runs: int = 0
    connector_failures: int = 0
    local_failures: int = 0


def _minutes_setting(name, default):
    value = int(getattr(settings, name, default))
    return max(value, 1)


@transaction.atomic
def _start_maintenance(user, *, trigger, include_network, now):
    running = (
        MaintenanceRun.objects.select_for_update()
        .filter(user=user, status=MaintenanceRun.Status.RUNNING)
        .first()
    )
    if running:
        stale_after = timedelta(
            minutes=_minutes_setting("FUNDBOARD_MAINTENANCE_STALE_MINUTES", 120)
        )
        if running.started_at <= now - stale_after:
            running.status = MaintenanceRun.Status.FAILED
            running.finished_at = now
            running.public_message = "Exécution interrompue récupérée automatiquement."
            running.save(update_fields=["status", "finished_at", "public_message"])
        else:
            raise MaintenanceAlreadyRunning(
                "Une maintenance est déjà en cours pour cet utilisateur."
            )
    try:
        return MaintenanceRun.objects.create(
            user=user,
            trigger=trigger,
            include_network=include_network,
        )
    except IntegrityError as exc:
        raise MaintenanceAlreadyRunning(
            "Une maintenance est déjà en cours pour cet utilisateur."
        ) from exc


def _maintain_virtual_portfolios(user, now, counters):
    portfolios = VirtualPortfolio.objects.filter(user=user, archived=False).iterator()
    day = timezone.localdate(now)
    for portfolio in portfolios:
        counters.virtual_portfolios += 1
        try:
            results = process_open_virtual_orders(portfolio, as_of=now)
            counters.virtual_orders_executed += sum(
                order.status == VirtualOrder.Status.EXECUTED for order in results
            )
            counters.virtual_orders_rejected += sum(
                order.status == VirtualOrder.Status.REJECTED for order in results
            )
            if not portfolio.performance_snapshots.filter(observed_at__date=day).exists():
                create_virtual_snapshot(portfolio, as_of=now)
        except Exception:
            counters.local_failures += 1
            logger.exception(
                "Virtual portfolio maintenance failed",
                extra={"event": "virtual_portfolio_failed", "portfolio_id": portfolio.pk},
            )


def _maintain_connectors(user, now, counters, *, force_network):
    due = Connection.objects.filter(user=user).exclude(status=Connection.Status.REVOKED)
    if not force_network:
        due = due.filter(Q(next_sync_at__isnull=True) | Q(next_sync_at__lte=now))
    success_delay = timedelta(
        minutes=_minutes_setting("FUNDBOARD_SYNC_INTERVAL_MINUTES", 360)
    )
    retry_delay = timedelta(
        minutes=_minutes_setting("FUNDBOARD_SYNC_RETRY_MINUTES", 30)
    )
    for connection in due.select_related("institution").iterator():
        try:
            connector = get_connector(connection.provider)
            if connector.import_only:
                continue
            result = sync_connection(
                connection,
                connector=connector,
                trigger=ConnectorSyncRun.Trigger.SCHEDULED,
            )
        except ConnectorError as exc:
            counters.connector_failures += 1
            connection.next_sync_at = now + retry_delay
            connection.save(update_fields=["next_sync_at", "updated_at"])
            logger.warning(
                "Scheduled connector synchronization failed: %s",
                exc.public_message,
                extra={
                    "event": "connector_sync_failed",
                    "connection_id": connection.pk,
                },
            )
        else:
            counters.connector_runs += 1
            connection.next_sync_at = now + success_delay
            connection.save(update_fields=["next_sync_at", "updated_at"])
            if result.status == ConnectorSyncRun.Status.PARTIAL:
                counters.connector_failures += 1


def _maintain_market_data(user, counters):
    try:
        refresh_exchange_rate()
    except Exception:
        counters.market_failures += 1
        logger.exception(
            "Scheduled exchange-rate refresh failed",
            extra={"event": "fx_refresh_failed"},
        )
    else:
        counters.fx_refreshed = True

    instruments = (
        Instrument.objects.filter(status=Instrument.Status.ACTIVE)
        .filter(
            Q(owner=user)
            | Q(positions__account__user=user)
            | Q(benchmark_preferences__user=user)
            | Q(virtual_watchlist_entries__portfolio__user=user)
        )
        .distinct()
        .iterator()
    )
    for instrument in instruments:
        try:
            refresh_instrument_market_data(
                user,
                instrument,
                include_history=False,
            )
        except Exception:
            counters.market_failures += 1
            logger.exception(
                "Scheduled market-data refresh failed",
                extra={
                    "event": "market_refresh_failed",
                    "instrument_id": instrument.pk,
                },
            )
        else:
            counters.market_refreshes += 1


def _finish_maintenance(run, counters, *, snapshot_issue_count):
    has_issues = bool(
        snapshot_issue_count
        or counters.local_failures
        or counters.market_failures
        or counters.connector_failures
    )
    run.status = (
        MaintenanceRun.Status.PARTIAL if has_issues else MaintenanceRun.Status.SUCCEEDED
    )
    run.finished_at = timezone.now()
    run.snapshot_created_count = counters.snapshot_created
    run.snapshot_existing_count = counters.snapshot_existing
    run.virtual_portfolio_count = counters.virtual_portfolios
    run.virtual_order_executed_count = counters.virtual_orders_executed
    run.virtual_order_rejected_count = counters.virtual_orders_rejected
    run.market_refresh_count = counters.market_refreshes
    run.market_failure_count = counters.market_failures
    run.fx_refresh_succeeded = counters.fx_refreshed
    run.connector_run_count = counters.connector_runs
    run.connector_failure_count = counters.connector_failures
    run.public_message = (
        "Maintenance terminée avec des éléments à contrôler."
        if has_issues
        else "Maintenance terminée."
    )
    run.details = {
        "snapshot_issue_count": snapshot_issue_count,
        "local_failure_count": counters.local_failures,
    }
    run.save()
    logger.info(
        "FundBoard maintenance finished",
        extra={
            "event": "maintenance_finished",
            "correlation_id": str(run.correlation_id),
            "status": run.status,
        },
    )
    return run


def run_user_maintenance(
    user,
    *,
    include_network=False,
    force_network=False,
    trigger=MaintenanceRun.Trigger.SCHEDULED,
    as_of=None,
):
    """Run cached local jobs, then optional due read-only connector syncs."""
    now = as_of or timezone.now()
    run = _start_maintenance(
        user,
        trigger=trigger,
        include_network=include_network,
        now=now,
    )
    counters = MaintenanceCounters()
    snapshot_issue_count = 0
    try:
        # Refresh remote inputs first when explicitly enabled. Derived snapshots
        # and simulated executions then consume the newest successfully stored
        # state, or the last valid cache if a provider failed.
        if include_network:
            _maintain_connectors(user, now, counters, force_network=force_network)
            _maintain_market_data(user, counters)
        try:
            snapshot = create_daily_snapshots(user, day=timezone.localdate(now))
        except IncompleteValuationError as exc:
            snapshot_issue_count = len(exc.issues)
        else:
            counters.snapshot_created = snapshot.created
            counters.snapshot_existing = snapshot.existing

        _maintain_virtual_portfolios(user, now, counters)
        return _finish_maintenance(
            run,
            counters,
            snapshot_issue_count=snapshot_issue_count,
        )
    except Exception:
        run.status = MaintenanceRun.Status.FAILED
        run.finished_at = timezone.now()
        run.public_message = "La maintenance a échoué ; consultez les journaux locaux."
        run.details = {"error_code": "internal_error"}
        run.save(update_fields=["status", "finished_at", "public_message", "details"])
        logger.exception(
            "FundBoard maintenance failed",
            extra={
                "event": "maintenance_failed",
                "correlation_id": str(run.correlation_id),
            },
        )
        raise

"""Read-only operational health checks for CLI and the personal dashboard."""

from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from FundBoard.models import Connection, ConnectorSyncRun, MaintenanceRun, VirtualOrder


@dataclass(frozen=True)
class OperationalHealth:
    status: str
    database_ok: bool
    pending_migration_count: int
    stale_maintenance_count: int
    stale_connector_run_count: int
    connection_attention_count: int
    overdue_connection_count: int
    open_virtual_order_count: int
    messages: tuple[str, ...]

    def as_dict(self):
        payload = asdict(self)
        payload["messages"] = list(self.messages)
        return payload


def operational_health(*, user=None, as_of=None):
    now = as_of or timezone.now()
    messages = []
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database_ok = False
        messages.append("La base de données ne répond pas.")

    pending_migrations = 0
    if database_ok:
        executor = MigrationExecutor(connection)
        pending_migrations = len(
            executor.migration_plan(executor.loader.graph.leaf_nodes())
        )
        if pending_migrations:
            messages.append(f"{pending_migrations} migration(s) restent à appliquer.")

    if not database_ok or pending_migrations:
        return OperationalHealth(
            status="ERROR",
            database_ok=database_ok,
            pending_migration_count=pending_migrations,
            stale_maintenance_count=0,
            stale_connector_run_count=0,
            connection_attention_count=0,
            overdue_connection_count=0,
            open_virtual_order_count=0,
            messages=tuple(messages),
        )

    cutoff = now - timedelta(hours=2)
    maintenance = MaintenanceRun.objects.filter(
        status=MaintenanceRun.Status.RUNNING,
        started_at__lt=cutoff,
    )
    connector_runs = ConnectorSyncRun.objects.filter(
        status=ConnectorSyncRun.Status.RUNNING,
        started_at__lt=cutoff,
    )
    connections = Connection.objects.exclude(status=Connection.Status.REVOKED)
    orders = VirtualOrder.objects.filter(status=VirtualOrder.Status.OPEN)
    if user is not None:
        maintenance = maintenance.filter(user=user)
        connector_runs = connector_runs.filter(connection__user=user)
        connections = connections.filter(user=user)
        orders = orders.filter(portfolio__user=user)

    stale_maintenance = maintenance.count()
    stale_connectors = connector_runs.count()
    attention = connections.filter(
        status__in=[Connection.Status.STALE, Connection.Status.ERROR]
    ).count()
    overdue = connections.filter(next_sync_at__lt=now).count()
    open_orders = orders.count()
    if stale_maintenance:
        messages.append(f"{stale_maintenance} maintenance(s) semblent interrompues.")
    if stale_connectors:
        messages.append(f"{stale_connectors} synchronisation(s) semblent interrompues.")
    if attention:
        messages.append(f"{attention} connexion(s) nécessitent une vérification.")
    if overdue:
        messages.append(f"{overdue} connexion(s) ont dépassé leur prochaine échéance.")

    is_error = not database_ok or bool(pending_migrations or stale_maintenance or stale_connectors)
    status = "ERROR" if is_error else ("WARNING" if attention or overdue else "OK")
    return OperationalHealth(
        status=status,
        database_ok=database_ok,
        pending_migration_count=pending_migrations,
        stale_maintenance_count=stale_maintenance,
        stale_connector_run_count=stale_connectors,
        connection_attention_count=attention,
        overdue_connection_count=overdue,
        open_virtual_order_count=open_orders,
        messages=tuple(messages),
    )

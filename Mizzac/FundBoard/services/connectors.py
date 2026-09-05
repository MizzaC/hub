"""Idempotent persistence and lifecycle services for read-only connectors."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from FundBoard.integrations.connectors import get_connector
from FundBoard.integrations.connectors.base import ConnectorError, SyncPayload
from FundBoard.models import (
    Account,
    Connection,
    ConnectorSyncRun,
    ExternalIdentifier,
    FinancialAuditEvent,
    Institution,
    Instrument,
    Position,
    Transaction,
)

from .audit import record_financial_event
from .transactions import IdempotencyConflict, persist_idempotently


@dataclass
class SyncCounters:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    rejected: int = 0


def _changed(instance, values):
    return any(getattr(instance, field) != value for field, value in values.items())


def _upsert_account(connection, remote, *, imported=False):
    values = {
        "institution": connection.institution,
        "name": remote.name[:255],
        "category": remote.category,
        "subtype": remote.subtype[:50],
        "currency": remote.currency.upper(),
        "balance": remote.balance,
        "iban_masked": remote.iban_masked[:34],
        "status": Account.Status.ACTIVE,
        "source": Account.Source.IMPORT if imported else Account.Source.PROVIDER,
        "metadata": dict(remote.metadata),
    }
    account = Account.objects.filter(
        user=connection.user,
        connection=connection,
        external_id=remote.external_id,
    ).first()
    created = account is None
    if created:
        account = Account(
            user=connection.user,
            connection=connection,
            external_id=remote.external_id,
            **values,
        )
        changed = True
    else:
        changed = _changed(account, values)
        for field, value in values.items():
            setattr(account, field, value)
    account.full_clean()
    account.save()
    return account, created, changed


def _upsert_instrument(connection, remote):
    identifier = ExternalIdentifier.objects.filter(
        user=connection.user,
        provider=connection.provider,
        external_id=remote.external_id,
        instrument__isnull=False,
    ).select_related("instrument").first()
    values = {
        "name": remote.name[:255],
        "ticker": remote.ticker[:30],
        "instrument_type": remote.instrument_type,
        "currency": remote.currency.upper(),
        "provider_identifiers": dict(remote.provider_identifiers),
        "blockchain": remote.blockchain[:50],
        "contract_address": remote.contract_address[:255],
        "status": Instrument.Status.ACTIVE,
    }
    created = identifier is None
    if created:
        instrument = Instrument(owner=connection.user, **values)
        instrument.full_clean()
        instrument.save()
        external = ExternalIdentifier(
            user=connection.user,
            provider=connection.provider,
            external_id=remote.external_id,
            instrument=instrument,
        )
        external.full_clean()
        external.save()
        return instrument, True, True
    instrument = identifier.instrument
    changed = _changed(instrument, values)
    for field, value in values.items():
        setattr(instrument, field, value)
    instrument.full_clean()
    instrument.save()
    return instrument, False, changed


def _upsert_position(remote, account_map, instrument_map, *, imported=False):
    account = account_map[remote.account_external_id]
    instrument = instrument_map[remote.instrument_external_id]
    values = {
        "quantity": remote.quantity,
        "current_unit_price": remote.current_unit_price,
        "current_value": remote.current_value,
        "value_currency": remote.value_currency.upper(),
        "valued_at": remote.valued_at,
        "source": Position.Source.IMPORT if imported else Position.Source.PROVIDER,
        "status": Position.Status.ACTIVE,
        "metadata": dict(remote.metadata),
    }
    position = Position.objects.filter(account=account, instrument=instrument).first()
    created = position is None
    if created:
        position = Position(account=account, instrument=instrument, **values)
        changed = True
    else:
        changed = _changed(position, values)
        for field, value in values.items():
            setattr(position, field, value)
    position.full_clean()
    position.save()
    return created, changed


def _persist_transaction(connection, remote, account_map, instrument_map, *, imported):
    candidate = Transaction(
        user=connection.user,
        account=account_map[remote.account_external_id],
        instrument=instrument_map.get(remote.instrument_external_id),
        external_id=remote.external_id,
        provider=connection.provider,
        transaction_type=remote.transaction_type,
        subtype=remote.subtype[:50],
        quantity=remote.quantity,
        unit_price=remote.unit_price,
        gross_amount=remote.gross_amount,
        fees=remote.fees,
        taxes=0,
        net_amount=remote.net_amount,
        currency=remote.currency.upper(),
        executed_at=remote.executed_at,
        value_date=remote.value_date,
        label=remote.label[:500],
        status=remote.status,
        source=Transaction.Source.IMPORT if imported else Transaction.Source.PROVIDER,
        idempotency_key=f"{connection.provider}:{remote.external_id}",
        metadata=dict(remote.metadata),
    )
    _, created = persist_idempotently(candidate)
    return created


def _start_run(connection, trigger):
    try:
        with transaction.atomic():
            return ConnectorSyncRun.objects.create(
                connection=connection,
                trigger=trigger,
                initial_sync=connection.last_synced_at is None,
                cursor_before=connection.sync_cursor,
            )
    except IntegrityError as exc:
        raise ConnectorError("sync_in_progress", "Une synchronisation est déjà en cours.") from exc


def _fail_run(run, error):
    run.status = ConnectorSyncRun.Status.FAILED
    run.finished_at = timezone.now()
    run.error_code = error.code
    run.public_message = error.public_message
    run.save(update_fields=["status", "finished_at", "error_code", "public_message"])


def _persist_payload(connection, payload, *, trigger, run=None):
    run = run or _start_run(connection, trigger)
    counters = SyncCounters(rejected=len(payload.issues))
    account_map = {}
    instrument_map = {}
    imported = trigger == ConnectorSyncRun.Trigger.IMPORT
    try:
        for remote in payload.accounts:
            try:
                with transaction.atomic():
                    account, created, changed = _upsert_account(
                        connection,
                        remote,
                        imported=imported,
                    )
                account_map[remote.external_id] = account
                counters.created += int(created)
                counters.updated += int(not created and changed)
                counters.skipped += int(not changed)
            except (ValidationError, IntegrityError, KeyError, ValueError, TypeError):
                counters.rejected += 1

        for remote in payload.instruments:
            try:
                with transaction.atomic():
                    instrument, created, changed = _upsert_instrument(connection, remote)
                instrument_map[remote.external_id] = instrument
                counters.created += int(created)
                counters.updated += int(not created and changed)
                counters.skipped += int(not changed)
            except (ValidationError, IntegrityError, KeyError, ValueError, TypeError):
                counters.rejected += 1

        for remote in payload.positions:
            try:
                with transaction.atomic():
                    created, changed = _upsert_position(
                        remote,
                        account_map,
                        instrument_map,
                        imported=imported,
                    )
                counters.created += int(created)
                counters.updated += int(not created and changed)
                counters.skipped += int(not changed)
            except (ValidationError, IntegrityError, KeyError, ValueError, TypeError):
                counters.rejected += 1

        for remote in payload.transactions:
            try:
                with transaction.atomic():
                    created = _persist_transaction(
                        connection,
                        remote,
                        account_map,
                        instrument_map,
                        imported=imported,
                    )
                counters.created += int(created)
                counters.skipped += int(not created)
            except (
                ValidationError,
                IntegrityError,
                IdempotencyConflict,
                KeyError,
                ValueError,
                TypeError,
            ):
                counters.rejected += 1

        now = timezone.now()
        connection.sync_cursor = payload.cursor
        connection.last_synced_at = now
        connection.last_error = ""
        connection.status = Connection.Status.ACTIVE
        connection.save(
            update_fields=["sync_cursor", "last_synced_at", "last_error", "status", "updated_at"]
        )
        received = sum(
            len(items)
            for items in (payload.accounts, payload.instruments, payload.positions, payload.transactions)
        )
        run.status = (
            ConnectorSyncRun.Status.PARTIAL
            if counters.rejected
            else ConnectorSyncRun.Status.SUCCEEDED
        )
        run.finished_at = now
        run.received_count = received
        run.created_count = counters.created
        run.updated_count = counters.updated
        run.skipped_count = counters.skipped
        run.rejected_count = counters.rejected
        run.public_message = (
            f"{counters.rejected} élément(s) invalide(s) ignoré(s)." if counters.rejected else ""
        )
        run.cursor_after = payload.cursor
        run.save()
        record_financial_event(
            connection.user,
            FinancialAuditEvent.Type.CONNECTOR_SYNC,
            connection,
            details={"run": str(run.correlation_id), "status": run.status},
        )
        return run
    except Exception:
        run.status = ConnectorSyncRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_code = "persistence"
        run.public_message = "La synchronisation n'a pas pu être enregistrée."
        run.save(update_fields=["status", "finished_at", "error_code", "public_message"])
        raise


def sync_connection(connection, *, connector=None, trigger=ConnectorSyncRun.Trigger.MANUAL):
    provider = connector or get_connector(connection.provider)
    run = _start_run(connection, trigger)
    try:
        payload = provider.sync(connection)
        if not isinstance(payload, SyncPayload):
            raise ConnectorError("invalid_response", "Le connecteur a renvoyé un format invalide.")
        return _persist_payload(connection, payload, trigger=trigger, run=run)
    except ConnectorError as exc:
        _fail_run(run, exc)
        connection.status = Connection.Status.ERROR
        connection.last_error = exc.public_message
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise
    except Exception as exc:
        safe_error = ConnectorError(
            "sync_failed",
            "La synchronisation a échoué sans modifier le dernier état valide.",
        )
        if run.status == ConnectorSyncRun.Status.RUNNING:
            _fail_run(run, safe_error)
        connection.status = Connection.Status.ERROR
        connection.last_error = safe_error.public_message
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise safe_error from exc


def import_connection_file(connection, content, filename, *, connector=None):
    provider = connector or get_connector(connection.provider)
    if not provider.import_only:
        raise ConnectorError("invalid_provider", "Ce connecteur n'accepte pas d'import local.")
    run = _start_run(connection, ConnectorSyncRun.Trigger.IMPORT)
    try:
        provider.validate_configuration(connection.configuration)
        payload = provider.parse(content, filename)
        return _persist_payload(
            connection,
            payload,
            trigger=ConnectorSyncRun.Trigger.IMPORT,
            run=run,
        )
    except ConnectorError as exc:
        _fail_run(run, exc)
        connection.status = Connection.Status.ERROR
        connection.last_error = exc.public_message
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise
    except Exception as exc:
        safe_error = ConnectorError("import_failed", "L'import local a échoué sans exposer son contenu.")
        if run.status == ConnectorSyncRun.Status.RUNNING:
            _fail_run(run, safe_error)
        connection.status = Connection.Status.ERROR
        connection.last_error = safe_error.public_message
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise safe_error from exc


def test_connection(connection, *, connector=None):
    provider = connector or get_connector(connection.provider)
    try:
        check = provider.test_connection(connection)
    except ConnectorError as exc:
        connection.status = Connection.Status.ERROR
        connection.last_error = exc.public_message
        connection.last_tested_at = timezone.now()
        connection.save(update_fields=["status", "last_error", "last_tested_at", "updated_at"])
        raise
    connection.status = Connection.Status.ACTIVE
    connection.last_error = ""
    connection.last_tested_at = timezone.now()
    connection.consent_expires_at = check.consent_expires_at
    connection.capabilities = list(check.capabilities)
    connection.save(
        update_fields=[
            "status",
            "last_error",
            "last_tested_at",
            "consent_expires_at",
            "capabilities",
            "updated_at",
        ]
    )
    record_financial_event(
        connection.user,
        FinancialAuditEvent.Type.CONNECTOR_TEST,
        connection,
        details={"status": "success"},
    )
    return check


def disconnect_connection(connection, *, connector=None):
    provider = connector or get_connector(connection.provider)
    provider.revoke(connection)
    connection.status = Connection.Status.REVOKED
    connection.secret_reference = ""
    connection.external_id = ""
    connection.sync_cursor = {}
    connection.next_sync_at = None
    connection.last_error = ""
    connection.save(
        update_fields=[
            "status",
            "secret_reference",
            "external_id",
            "sync_cursor",
            "next_sync_at",
            "last_error",
            "updated_at",
        ]
    )
    record_financial_event(
        connection.user,
        FinancialAuditEvent.Type.CONNECTOR_DISCONNECT,
        connection,
    )


def institution_for_provider(provider, display_name, *, country=""):
    type_by_provider = {
        "enable_banking": Institution.Type.BANK,
        "binance": Institution.Type.CRYPTO_EXCHANGE,
        "ledger_live": Institution.Type.CUSTODIAN,
        "trade_republic": Institution.Type.BROKER,
    }
    slug = f"{provider}-{slugify(display_name)}"[:255]
    institution, _ = Institution.objects.get_or_create(
        slug=slug,
        defaults={
            "name": display_name,
            "institution_type": type_by_provider.get(provider, Institution.Type.OTHER),
            "country_code": country,
            "capabilities": ["read_only"],
        },
    )
    return institution

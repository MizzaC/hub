import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.utils import timezone

from FundBoard.models import (
    Account,
    FinancialAuditEvent,
    ImportBatch,
    ImportChange,
    ImportIssue,
    Instrument,
    Loan,
    Position,
    RealEstate,
    Transaction,
)
from FundBoard.services.audit import record_financial_event
from FundBoard.services.transactions import IdempotencyConflict, persist_idempotently

from .parser import RowIssue

PROCESS_ORDER = {
    "Accounts": 0,
    "Instruments": 1,
    "Loans": 2,
    "Positions": 3,
    "Transactions": 4,
    "RealEstate": 5,
}

TRACKED_FIELDS = {
    "Account": (
        "manual_reference",
        "name",
        "category",
        "subtype",
        "balance",
        "currency",
        "ownership_share",
        "iban_masked",
        "status",
        "source",
    ),
    "Instrument": (
        "owner",
        "manual_reference",
        "name",
        "instrument_type",
        "ticker",
        "isin",
        "market_mic",
        "currency",
        "country_code",
        "sector",
        "blockchain",
        "contract_address",
        "status",
    ),
    "Position": (
        "account",
        "instrument",
        "quantity",
        "average_unit_cost",
        "cost_basis",
        "current_unit_price",
        "current_value",
        "value_currency",
        "valued_at",
        "source",
        "status",
    ),
    "Transaction": (
        "user",
        "account",
        "instrument",
        "transaction_type",
        "subtype",
        "quantity",
        "unit_price",
        "gross_amount",
        "fees",
        "taxes",
        "net_amount",
        "currency",
        "executed_at",
        "value_date",
        "label",
        "status",
        "source",
        "idempotency_key",
    ),
    "Loan": (
        "user",
        "account",
        "manual_reference",
        "name",
        "loan_type",
        "currency",
        "original_principal",
        "outstanding_principal",
        "balance_date",
        "nominal_rate",
        "apr",
        "duration_months",
        "start_date",
        "maturity_date",
        "payment_amount",
        "insurance_amount",
        "insurance_rate",
        "initial_fees",
        "deferred_months",
        "archived",
    ),
    "RealEstate": (
        "user",
        "linked_loan",
        "manual_reference",
        "name",
        "property_type",
        "address",
        "surface_sqm",
        "ownership_share",
        "currency",
        "purchase_price",
        "purchase_costs",
        "renovation_costs",
        "estimated_value",
        "valuation_date",
        "valuation_source",
        "monthly_rent",
        "monthly_charges",
        "annual_property_tax",
        "annual_insurance",
        "annual_other_costs",
        "vacancy_rate",
        "archived",
    ),
}

MODEL_MAP = {
    "Account": Account,
    "Instrument": Instrument,
    "Position": Position,
    "Transaction": Transaction,
    "Loan": Loan,
    "RealEstate": RealEstate,
}


class DuplicateImportError(ValueError):
    def __init__(self, batch):
        self.batch = batch
        super().__init__("Ce fichier a déjà été importé pour cet utilisateur.")


class RollbackRefusedError(ValueError):
    pass


@dataclass(frozen=True)
class PendingChange:
    sheet: str
    row_number: int
    model_name: str
    object_pk: int
    action: str
    before_data: dict
    after_data: dict


@dataclass(frozen=True)
class ImportReport:
    total_rows: int
    created_rows: int
    updated_rows: int
    skipped_rows: int
    invalid_rows: int
    issues: tuple[RowIssue, ...]
    batch: ImportBatch | None = None


def file_sha256(content):
    return hashlib.sha256(content).hexdigest()


def _json_value(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialize_instance(instance):
    values = {}
    for name in TRACKED_FIELDS[type(instance).__name__]:
        field = instance._meta.get_field(name)
        value = getattr(instance, field.attname if field.is_relation else name)
        values[name] = _json_value(value)
    return values


def _set_fields(instance, data, fields, defaults=None):
    defaults = defaults or {}
    adding = instance.pk is None
    for name in fields:
        if name not in data:
            if adding and name in defaults:
                setattr(instance, name, defaults[name])
            continue
        value = data[name]
        if value in (None, "") and adding and name in defaults:
            value = defaults[name]
        field = instance._meta.get_field(name)
        if value in (None, "") and field.null:
            value = None
        elif value is None and field.blank:
            value = ""
        setattr(instance, name, value)


def _save(instance, row, before_data):
    instance.full_clean()
    instance.save()
    after_data = serialize_instance(instance)
    if before_data == after_data:
        return "skipped", None
    action = ImportChange.Action.UPDATED if before_data else ImportChange.Action.CREATED
    return (
        "updated" if before_data else "created",
        PendingChange(
            row.sheet,
            row.row_number,
            type(instance).__name__,
            instance.pk,
            action,
            before_data,
            after_data,
        ),
    )


def _required_reference(data, name):
    value = str(data.get(name, "")).strip()
    if not value:
        raise ValidationError({name: "Référence obligatoire manquante."})
    return value


def _account(user, reference):
    try:
        return Account.objects.get(user=user, manual_reference=reference)
    except Account.DoesNotExist as exc:
        raise ValidationError({"account_reference": f"Compte inconnu : {reference}."}) from exc


def _instrument(user, reference):
    try:
        return Instrument.objects.get(owner=user, manual_reference=reference)
    except Instrument.DoesNotExist as exc:
        raise ValidationError(
            {"instrument_reference": f"Instrument privé inconnu : {reference}."}
        ) from exc


def _apply_account(user, row):
    reference = _required_reference(row.data, "manual_reference")
    instance = Account.objects.filter(user=user, manual_reference=reference).first()
    before = serialize_instance(instance) if instance else {}
    instance = instance or Account(user=user, manual_reference=reference)
    _set_fields(
        instance,
        row.data,
        [
            "manual_reference",
            "name",
            "category",
            "subtype",
            "balance",
            "currency",
            "ownership_share",
            "iban_masked",
            "status",
        ],
        {
            "balance": Decimal("0"),
            "ownership_share": Decimal("100"),
            "subtype": "",
            "iban_masked": "",
            "status": Account.Status.ACTIVE,
        },
    )
    instance.source = Account.Source.IMPORT
    return _save(instance, row, before)


def _apply_instrument(user, row):
    reference = _required_reference(row.data, "manual_reference")
    instance = Instrument.objects.filter(owner=user, manual_reference=reference).first()
    before = serialize_instance(instance) if instance else {}
    instance = instance or Instrument(owner=user, manual_reference=reference)
    _set_fields(
        instance,
        row.data,
        [
            "manual_reference",
            "name",
            "instrument_type",
            "ticker",
            "isin",
            "market_mic",
            "currency",
            "country_code",
            "sector",
            "blockchain",
            "contract_address",
            "status",
        ],
        {
            "ticker": "",
            "isin": "",
            "market_mic": "",
            "country_code": "",
            "sector": "",
            "blockchain": "",
            "contract_address": "",
            "status": Instrument.Status.ACTIVE,
        },
    )
    return _save(instance, row, before)


def _apply_position(user, row):
    account = _account(user, _required_reference(row.data, "account_reference"))
    instrument = _instrument(user, _required_reference(row.data, "instrument_reference"))
    instance = Position.objects.filter(account=account, instrument=instrument).first()
    before = serialize_instance(instance) if instance else {}
    instance = instance or Position(account=account, instrument=instrument)
    _set_fields(
        instance,
        row.data,
        [
            "quantity",
            "average_unit_cost",
            "cost_basis",
            "current_unit_price",
            "current_value",
            "value_currency",
            "valued_at",
            "status",
        ],
        {"status": Position.Status.ACTIVE},
    )
    instance.source = Position.Source.IMPORT
    return _save(instance, row, before)


def _transaction_key(data):
    supplied = str(data.get("idempotency_key") or "").strip()
    if supplied:
        return f"import:{supplied}"
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return f"import:row:{hashlib.sha256(encoded).hexdigest()}"


def _apply_transaction(user, row):
    account = _account(user, _required_reference(row.data, "account_reference"))
    instrument_reference = str(row.data.get("instrument_reference") or "").strip()
    instrument = _instrument(user, instrument_reference) if instrument_reference else None
    candidate = Transaction(user=user, account=account, instrument=instrument)
    _set_fields(
        candidate,
        row.data,
        [
            "transaction_type",
            "subtype",
            "quantity",
            "unit_price",
            "gross_amount",
            "fees",
            "taxes",
            "net_amount",
            "currency",
            "executed_at",
            "value_date",
            "label",
            "status",
        ],
        {
            "subtype": "",
            "fees": Decimal("0"),
            "taxes": Decimal("0"),
            "label": "",
            "status": Transaction.Status.BOOKED,
        },
    )
    candidate.source = Transaction.Source.IMPORT
    candidate.idempotency_key = _transaction_key(row.data)
    instance, created = persist_idempotently(candidate)
    if not created:
        return "skipped", None
    return (
        "created",
        PendingChange(
            row.sheet,
            row.row_number,
            "Transaction",
            instance.pk,
            ImportChange.Action.CREATED,
            {},
            serialize_instance(instance),
        ),
    )


def _apply_loan(user, row):
    reference = _required_reference(row.data, "manual_reference")
    instance = Loan.objects.filter(user=user, manual_reference=reference).first()
    before = serialize_instance(instance) if instance else {}
    instance = instance or Loan(user=user, manual_reference=reference)
    account_reference = str(row.data.get("account_reference") or "").strip()
    instance.account = _account(user, account_reference) if account_reference else None
    _set_fields(
        instance,
        row.data,
        [
            "manual_reference",
            "name",
            "loan_type",
            "currency",
            "original_principal",
            "outstanding_principal",
            "balance_date",
            "nominal_rate",
            "apr",
            "duration_months",
            "start_date",
            "maturity_date",
            "payment_amount",
            "insurance_amount",
            "insurance_rate",
            "initial_fees",
            "deferred_months",
        ],
        {
            "insurance_amount": Decimal("0"),
            "initial_fees": Decimal("0"),
            "deferred_months": 0,
        },
    )
    instance.archived = False
    return _save(instance, row, before)


def _apply_real_estate(user, row):
    reference = _required_reference(row.data, "manual_reference")
    instance = RealEstate.objects.filter(user=user, manual_reference=reference).first()
    before = serialize_instance(instance) if instance else {}
    instance = instance or RealEstate(user=user, manual_reference=reference)
    loan_reference = str(row.data.get("loan_reference") or "").strip()
    if loan_reference:
        try:
            instance.linked_loan = Loan.objects.get(user=user, manual_reference=loan_reference)
        except Loan.DoesNotExist as exc:
            raise ValidationError(
                {"loan_reference": f"Prêt inconnu : {loan_reference}."}
            ) from exc
    else:
        instance.linked_loan = None
    _set_fields(
        instance,
        row.data,
        [
            "manual_reference",
            "name",
            "property_type",
            "address",
            "surface_sqm",
            "ownership_share",
            "currency",
            "purchase_price",
            "purchase_costs",
            "renovation_costs",
            "estimated_value",
            "valuation_date",
            "valuation_source",
            "monthly_rent",
            "monthly_charges",
            "annual_property_tax",
            "annual_insurance",
            "annual_other_costs",
            "vacancy_rate",
        ],
        {
            "address": "",
            "ownership_share": Decimal("100"),
            "purchase_costs": Decimal("0"),
            "renovation_costs": Decimal("0"),
            "valuation_source": "manual",
            "monthly_rent": Decimal("0"),
            "monthly_charges": Decimal("0"),
            "annual_property_tax": Decimal("0"),
            "annual_insurance": Decimal("0"),
            "annual_other_costs": Decimal("0"),
            "vacancy_rate": Decimal("0"),
        },
    )
    instance.archived = False
    return _save(instance, row, before)


APPLIERS = {
    "Accounts": _apply_account,
    "Instruments": _apply_instrument,
    "Positions": _apply_position,
    "Transactions": _apply_transaction,
    "RealEstate": _apply_real_estate,
    "Loans": _apply_loan,
}


def _validation_issues(row, error):
    if hasattr(error, "message_dict"):
        return [
            RowIssue(
                row.sheet,
                row.row_number,
                column,
                "validation",
                str(message),
                "[masqué]" if column == "address" else str(row.data.get(column, ""))[:200],
            )
            for column, messages in error.message_dict.items()
            for message in messages
        ]
    return [RowIssue(row.sheet, row.row_number, "", "validation", str(error))]


def _execute(user, document):
    issues = list(document.issues)
    created = updated = skipped = 0
    changes_by_object = {}
    rows = sorted(document.rows, key=lambda item: (PROCESS_ORDER[item.sheet], item.row_number))
    for row in rows:
        try:
            with db_transaction.atomic():
                outcome, change = APPLIERS[row.sheet](user, row)
        except ValidationError as exc:
            issues.extend(_validation_issues(row, exc))
            continue
        except (IntegrityError, IdempotencyConflict, ValueError, TypeError) as exc:
            issues.append(RowIssue(row.sheet, row.row_number, "", "conflict", str(exc)))
            continue
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1
        if change:
            key = (change.model_name, change.object_pk)
            previous = changes_by_object.get(key)
            if previous:
                change = PendingChange(
                    previous.sheet,
                    previous.row_number,
                    change.model_name,
                    change.object_pk,
                    previous.action,
                    previous.before_data,
                    change.after_data,
                )
            changes_by_object[key] = change
    invalid_keys = {(issue.sheet, issue.row_number) for issue in issues}
    parsed_invalid_keys = {
        (issue.sheet, issue.row_number) for issue in document.issues
    }
    total = len(rows) + len(parsed_invalid_keys)
    return (
        ImportReport(total, created, updated, skipped, len(invalid_keys), tuple(issues)),
        list(changes_by_object.values()),
    )


def preview_import(user, document):
    with db_transaction.atomic():
        report, _ = _execute(user, document)
        db_transaction.set_rollback(True)
    return report


def commit_import(user, document, *, file_name, file_format, content):
    digest = file_sha256(content)
    existing = (
        ImportBatch.objects.filter(user=user, file_sha256=digest)
        .exclude(status=ImportBatch.Status.ROLLED_BACK)
        .first()
    )
    if existing:
        raise DuplicateImportError(existing)
    batch = ImportBatch.objects.create(
        user=user,
        file_name=file_name[:255],
        file_format=file_format,
        schema_version=document.schema_version,
        file_sha256=digest,
    )
    report, changes = _execute(user, document)
    ImportIssue.objects.bulk_create(
        [
            ImportIssue(
                batch=batch,
                sheet=issue.sheet,
                row_number=issue.row_number,
                column=issue.column,
                code=issue.code,
                message=issue.message,
                value_preview=issue.value_preview,
            )
            for issue in report.issues
        ]
    )
    ImportChange.objects.bulk_create(
        [
            ImportChange(
                batch=batch,
                sheet=change.sheet,
                row_number=change.row_number,
                model_name=change.model_name,
                object_pk=change.object_pk,
                action=change.action,
                before_data=change.before_data,
                after_data=change.after_data,
            )
            for change in changes
        ]
    )
    batch.total_rows = report.total_rows
    batch.created_rows = report.created_rows
    batch.updated_rows = report.updated_rows
    batch.skipped_rows = report.skipped_rows
    batch.invalid_rows = report.invalid_rows
    if report.invalid_rows:
        batch.status = ImportBatch.Status.PARTIAL if changes or report.skipped_rows else ImportBatch.Status.FAILED
    else:
        batch.status = ImportBatch.Status.COMPLETED
    batch.completed_at = timezone.now()
    batch.save(
        update_fields=[
            "total_rows",
            "created_rows",
            "updated_rows",
            "skipped_rows",
            "invalid_rows",
            "status",
            "completed_at",
        ]
    )
    record_financial_event(
        user,
        FinancialAuditEvent.Type.IMPORT,
        batch,
        details={
            "format": file_format,
            "status": batch.status,
            "created_rows": batch.created_rows,
            "updated_rows": batch.updated_rows,
            "invalid_rows": batch.invalid_rows,
        },
    )
    return ImportReport(
        report.total_rows,
        report.created_rows,
        report.updated_rows,
        report.skipped_rows,
        report.invalid_rows,
        report.issues,
        batch,
    )


def _restore(instance, values):
    for name, value in values.items():
        field = instance._meta.get_field(name)
        if field.is_relation:
            setattr(instance, field.attname, value)
        else:
            setattr(instance, name, field.to_python(value))
    instance.full_clean()
    instance.save()


def _related_instances(instance):
    for relation in instance._meta.related_objects:
        try:
            related = getattr(instance, relation.get_accessor_name())
        except ObjectDoesNotExist:
            continue
        if hasattr(related, "all"):
            yield from related.all()
        elif related is not None:
            yield related


def rollback_import(batch):
    if batch.status == ImportBatch.Status.ROLLED_BACK:
        return batch
    changes = list(batch.changes.order_by("-pk"))
    with db_transaction.atomic():
        resolved = []
        created_keys = {
            (change.model_name, change.object_pk)
            for change in changes
            if change.action == ImportChange.Action.CREATED
        }
        for change in changes:
            model = MODEL_MAP[change.model_name]
            instance = model.objects.filter(pk=change.object_pk).first()
            if not instance or serialize_instance(instance) != change.after_data:
                raise RollbackRefusedError(
                    "Annulation refusée : un objet importé a été supprimé ou modifié depuis le lot."
                )
            resolved.append((change, instance))
            if change.action == ImportChange.Action.CREATED:
                unknown_dependencies = [
                    related
                    for related in _related_instances(instance)
                    if (type(related).__name__, related.pk) not in created_keys
                ]
                if unknown_dependencies:
                    raise RollbackRefusedError(
                        "Annulation refusée : des données dépendent désormais d'un objet importé."
                    )
        for change, instance in resolved:
            if change.action == ImportChange.Action.CREATED:
                try:
                    instance.delete()
                except (IntegrityError, ProtectedError, RestrictedError) as exc:
                    raise RollbackRefusedError(
                        "Annulation refusée : des données dépendent désormais d'un objet importé."
                    ) from exc
            else:
                _restore(instance, change.before_data)
        batch.status = ImportBatch.Status.ROLLED_BACK
        batch.rolled_back_at = timezone.now()
        batch.save(update_fields=["status", "rolled_back_at"])
        record_financial_event(
            batch.user,
            FinancialAuditEvent.Type.IMPORT_ROLLBACK,
            batch,
        )
    return batch

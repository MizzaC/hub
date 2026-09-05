"""Transaction idempotence, transfer linking and performance classification."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction as db_transaction

from FundBoard.models import Transaction

from .performance import FlowKind, PerformanceFlow


class IdempotencyConflict(ValueError):
    """A key already represents another canonical transaction payload."""


IDEMPOTENT_FIELDS = (
    "account_id",
    "instrument_id",
    "provider",
    "external_id",
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
)


def _same_payload(left, right):
    return all(getattr(left, field) == getattr(right, field) for field in IDEMPOTENT_FIELDS)


def persist_idempotently(candidate):
    """Insert a validated transaction once, or return its exact prior insert.

    A reused key with different canonical data fails loudly instead of mutating
    the previously imported operation.
    """
    if candidate.pk:
        raise ValueError("La transaction candidate doit être nouvelle.")
    candidate.clean()
    if not candidate.idempotency_key:
        raise ValidationError({"idempotency_key": "Une clé d'idempotence est requise."})

    lookup = {
        "user_id": candidate.user_id,
        "idempotency_key": candidate.idempotency_key,
    }
    existing = Transaction.objects.filter(**lookup).first()
    if existing:
        if _same_payload(existing, candidate):
            return existing, False
        raise IdempotencyConflict("Cette clé d'idempotence correspond à une autre opération.")

    candidate.full_clean()
    try:
        with db_transaction.atomic():
            candidate.save(force_insert=True)
    except IntegrityError:
        existing = Transaction.objects.filter(**lookup).first()
        if existing and _same_payload(existing, candidate):
            return existing, False
        raise
    return candidate, True


def link_internal_transfers(first, second):
    """Atomically link the two opposite legs of an internal transfer."""
    if not first.pk or not second.pk:
        raise ValueError("Les deux transactions doivent être enregistrées.")
    if first.pk == second.pk:
        raise ValueError("Une transaction ne peut pas être liée à elle-même.")
    first.linked_transfer = second
    second.linked_transfer = first
    first.full_clean()
    second.full_clean()
    with db_transaction.atomic():
        first.save(update_fields=["linked_transfer", "updated_at"])
        second.save(update_fields=["linked_transfer", "updated_at"])
    return first, second


def performance_flow_from_transaction(transaction):
    """Map a booked canonical transaction to a portfolio performance flow.

    Buys and sells only change portfolio composition, so they produce no
    portfolio-level cash flow. Cancelled transactions are ignored as well.
    """
    if transaction.status == "CANCELLED":
        return None
    if transaction.transaction_type == "TRANSFER":
        kind = FlowKind.INTERNAL if transaction.is_internal_transfer else FlowKind.EXTERNAL
    elif transaction.transaction_type in {"DEPOSIT", "WITHDRAWAL"}:
        kind = FlowKind.EXTERNAL
    elif transaction.transaction_type in {"DIVIDEND", "INTEREST"}:
        kind = FlowKind.INCOME
    elif transaction.transaction_type == "FEE":
        kind = FlowKind.FEE
    elif transaction.transaction_type == "TAX":
        kind = FlowKind.TAX
    else:
        return None
    occurred_on = transaction.executed_at
    if not isinstance(occurred_on, date):
        occurred_on = occurred_on.date()
    elif hasattr(occurred_on, "date"):
        occurred_on = occurred_on.date()
    return PerformanceFlow(
        amount=transaction.net_amount,
        occurred_on=occurred_on,
        kind=kind,
    )

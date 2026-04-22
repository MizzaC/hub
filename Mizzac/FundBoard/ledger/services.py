from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.db import transaction as db_transaction

from FundBoard.models import Asset, Leg, Transaction

DEFAULT_TOLERANCE = Decimal("0.01")


class LedgerValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LegInput:
    account_id: int
    asset_id: int
    quantity: Decimal
    value_reference: Decimal
    unit_price_reference: Decimal | None = None
    reference_currency: str = "EUR"
    is_fee: bool = False
    is_adjustment: bool = False
    adjustment_type: str | None = None


def _normalize_decimal(value: Decimal | int | str | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _validate_leg_input(legs: Iterable[LegInput]) -> list[LegInput]:
    out = list(legs)
    if not out:
        raise LedgerValidationError("A transaction must contain at least one leg.")

    for leg in out:
        quantity = _normalize_decimal(leg.quantity)
        value_ref = _normalize_decimal(leg.value_reference)
        if quantity == 0:
            raise LedgerValidationError("Leg quantity cannot be zero.")
        if value_ref == 0:
            raise LedgerValidationError("Leg value_reference cannot be zero.")
        if leg.is_adjustment and not leg.adjustment_type:
            raise LedgerValidationError("Adjustment leg requires adjustment_type.")
    return out


@db_transaction.atomic
def post_transaction(
    *,
    payload: dict,
    legs: Iterable[LegInput],
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> Transaction:
    leg_inputs = _validate_leg_input(legs)
    tolerance = _normalize_decimal(tolerance)

    trx = Transaction.objects.create(
        user=payload["user"],
        trx_type=payload["trx_type"],
        executed_at=payload.get("executed_at"),
        description=payload.get("description"),
        external_reference=payload.get("external_reference"),
        tolerance_applied=tolerance,
    )

    txn_user_id = trx.user_id
    account_ids = {leg.account_id for leg in leg_inputs}
    asset_ids = {leg.asset_id for leg in leg_inputs}

    valid_account_ids = set(
        trx.user.account_set.filter(pk__in=account_ids).values_list("id", flat=True)
    )
    if valid_account_ids != account_ids:
        raise LedgerValidationError("All legs must reference accounts owned by the transaction user.")

    valid_asset_ids = set(Asset.objects.filter(pk__in=asset_ids).values_list("id", flat=True))
    if valid_asset_ids != asset_ids:
        raise LedgerValidationError("One or more legs reference a non-existing asset.")

    leg_rows: list[Leg] = []
    for leg in leg_inputs:
        leg_rows.append(
            Leg(
                transaction=trx,
                account_id=leg.account_id,
                asset_id=leg.asset_id,
                quantity=_normalize_decimal(leg.quantity),
                unit_price_reference=(
                    _normalize_decimal(leg.unit_price_reference)
                    if leg.unit_price_reference is not None
                    else None
                ),
                value_reference=_normalize_decimal(leg.value_reference),
                reference_currency=leg.reference_currency,
                is_fee=leg.is_fee,
                is_adjustment=leg.is_adjustment,
                adjustment_type=leg.adjustment_type,
            )
        )
    Leg.objects.bulk_create(leg_rows)

    delta = abs(sum((_normalize_decimal(leg.value_reference) for leg in leg_inputs), Decimal("0")))
    trx.integrity_delta = delta

    if delta == 0:
        trx.is_balanced = True
        trx.save(update_fields=["integrity_delta", "is_balanced", "tolerance_applied", "updated_at"])
        return trx

    if delta <= tolerance:
        first_leg = leg_rows[0]
        Leg.objects.create(
            transaction=trx,
            account=first_leg.account,
            asset=first_leg.asset,
            quantity=Decimal("0.000000000001"),
            value_reference=-delta,
            reference_currency=first_leg.reference_currency,
            is_adjustment=True,
            adjustment_type="ROUNDING",
        )
        trx.is_balanced = True
        trx.integrity_delta = Decimal("0")
        trx.save(update_fields=["integrity_delta", "is_balanced", "tolerance_applied", "updated_at"])
        return trx

    trx.is_balanced = False
    trx.save(update_fields=["integrity_delta", "is_balanced", "tolerance_applied", "updated_at"])
    raise LedgerValidationError(
        f"Transaction integrity delta {delta} exceeds tolerance {tolerance}."
    )

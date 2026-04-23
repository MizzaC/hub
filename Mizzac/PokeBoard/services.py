from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from .models import CollectibleValuation, CollectionOperation, OwnedLot


ZERO = Decimal("0")


@dataclass
class LotMarketSnapshot:
    lot: OwnedLot
    valuation: CollectibleValuation | None
    current_unit_value: Decimal | None
    current_total_value: Decimal | None
    unrealized_pnl: Decimal | None


def decimal_or_zero(value) -> Decimal:
    return value if value is not None else ZERO


def compute_operation_total(operation_type: str, quantity: Decimal, unit_price: Decimal | None, fees: Decimal | None) -> Decimal:
    qty = abs(quantity or ZERO)
    unit = unit_price or ZERO
    fee_amount = fees or ZERO
    gross = qty * unit
    if operation_type == "SELL":
        return gross - fee_amount
    if operation_type in {"BUY", "ADD"}:
        return gross + fee_amount
    if operation_type == "ADJUST" and quantity > 0:
        return gross + fee_amount
    return gross


def _consume_fifo_batches(batches: deque[list[Decimal]], quantity: Decimal) -> Decimal:
    remaining = quantity
    consumed_cost = ZERO
    while remaining > ZERO and batches:
        batch_qty, batch_unit_cost = batches[0]
        take = min(batch_qty, remaining)
        consumed_cost += take * batch_unit_cost
        batch_qty -= take
        remaining -= take
        if batch_qty <= ZERO:
            batches.popleft()
        else:
            batches[0][0] = batch_qty
    return consumed_cost


def recompute_lot_metrics(lot: OwnedLot) -> OwnedLot:
    operations = list(lot.operations.order_by("operation_date", "id"))
    batches: deque[list[Decimal]] = deque()
    realized_total = ZERO

    for operation in operations:
        signed_qty = operation.signed_quantity
        if signed_qty > ZERO:
            batch_qty = signed_qty
            unit_cost = ZERO
            if batch_qty and operation.total_price is not None:
                unit_cost = decimal_or_zero(operation.total_price) / batch_qty
            batches.append([batch_qty, unit_cost])
            if operation.realized_pnl is not None:
                operation.realized_pnl = None
                operation.save(update_fields=["realized_pnl", "updated_at"])
            continue

        if signed_qty < ZERO:
            quantity_to_remove = abs(signed_qty)
            consumed_cost = _consume_fifo_batches(batches, quantity_to_remove)
            if operation.operation_type == "SELL":
                realized = decimal_or_zero(operation.total_price) - consumed_cost
                realized_total += realized
                if operation.realized_pnl != realized:
                    operation.realized_pnl = realized
                    operation.save(update_fields=["realized_pnl", "updated_at"])
            elif operation.realized_pnl is not None:
                operation.realized_pnl = None
                operation.save(update_fields=["realized_pnl", "updated_at"])

    remaining_quantity = sum((batch[0] for batch in batches), ZERO)
    acquisition_total = sum((batch[0] * batch[1] for batch in batches), ZERO)
    average_unit_cost = None
    if remaining_quantity > ZERO:
        average_unit_cost = acquisition_total / remaining_quantity

    lot.remaining_quantity = remaining_quantity
    lot.acquisition_total = acquisition_total
    lot.average_unit_cost = average_unit_cost
    lot.realized_pnl_total = realized_total
    lot.save(
        update_fields=[
            "remaining_quantity",
            "acquisition_total",
            "average_unit_cost",
            "realized_pnl_total",
            "updated_at",
        ]
    )
    return lot


def latest_valuation_for_lot(lot: OwnedLot) -> CollectibleValuation | None:
    return (
        lot.collectible.valuations.filter(**lot.valuation_lookup())
        .order_by("-valued_at", "-id")
        .first()
    )


def build_market_snapshot(lot: OwnedLot) -> LotMarketSnapshot:
    valuation = latest_valuation_for_lot(lot)
    if not valuation:
        return LotMarketSnapshot(
            lot=lot,
            valuation=None,
            current_unit_value=None,
            current_total_value=None,
            unrealized_pnl=None,
        )

    current_unit_value = valuation.unit_value
    current_total = lot.remaining_quantity * current_unit_value
    unrealized = None
    if lot.average_unit_cost is not None:
        unrealized = (current_unit_value - lot.average_unit_cost) * lot.remaining_quantity

    return LotMarketSnapshot(
        lot=lot,
        valuation=valuation,
        current_unit_value=current_unit_value,
        current_total_value=current_total,
        unrealized_pnl=unrealized,
    )


def hydrate_lots_with_market_data(lots):
    hydrated = []
    for lot in lots:
        snapshot = build_market_snapshot(lot)
        lot.latest_valuation = snapshot.valuation
        lot.current_unit_value = snapshot.current_unit_value
        lot.current_total_value = snapshot.current_total_value
        lot.unrealized_pnl = snapshot.unrealized_pnl
        hydrated.append(lot)
    return hydrated


def lots_needing_valuation(user, include_fresh: bool = False, stale_after_days: int = 90):
    threshold = timezone.now().date() - timedelta(days=stale_after_days)
    lots = OwnedLot.objects.filter(user=user, remaining_quantity__gt=ZERO).select_related(
        "collectible",
        "collectible__extension",
        "collectible__extension__series",
        "collectible__card_details",
        "collectible__sealed_details",
    )
    lots = hydrate_lots_with_market_data(list(lots))
    items = []
    for lot in lots:
        valuation = getattr(lot, "latest_valuation", None)
        lot.needs_valuation = valuation is None or valuation.valued_at < threshold
        if valuation is None:
            lot.days_since_valuation = None
        else:
            lot.days_since_valuation = (timezone.now().date() - valuation.valued_at).days
        if include_fresh or lot.needs_valuation:
            items.append(lot)
    return items


def build_report_rows(operations):
    rows = []
    for operation in operations:
        lot = operation.lot
        snapshot = build_market_snapshot(lot)
        rows.append(
            {
                "date": operation.operation_date,
                "item": lot.collectible.display_name,
                "kind": lot.collectible.get_kind_display(),
                "series": lot.collectible.extension.series.name,
                "extension": lot.collectible.extension.name,
                "extension_code": lot.collectible.extension.code,
                "description": lot.description_text,
                "language": lot.get_language_display(),
                "card_condition": lot.get_card_condition_display() if lot.card_condition else None,
                "sealed_condition": lot.get_sealed_condition_display() if lot.sealed_condition else None,
                "is_graded": lot.is_graded,
                "grading_company": lot.grading_company,
                "grading_grade": lot.grading_grade,
                "operation_label": operation.get_operation_type_display(),
                "platform": operation.platform or lot.platform or "-",
                "quantity": operation.display_quantity,
                "unit_price": operation.unit_price,
                "total": operation.total_price,
                "current_unit_value": snapshot.current_unit_value,
                "valuation_date": snapshot.valuation.valued_at if snapshot.valuation else None,
                "pnl": snapshot.unrealized_pnl,
                "current_value": snapshot.current_total_value,
                "realized_pnl": operation.realized_pnl,
            }
        )
    return rows


def top_extensions_for_user(user, limit: int = 5):
    return (
        OwnedLot.objects.filter(user=user, remaining_quantity__gt=ZERO)
        .values("collectible__extension__name")
        .annotate(total=Count("id"))
        .order_by("-total", "collectible__extension__name")[:limit]
    )

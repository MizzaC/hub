"""Paper-trading engine using only prices already persisted in FundBoard.

This module contains no connector, broker client or network call. Virtual models
are deliberately distinct from Account, Position and Transaction.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from FundBoard.models import (
    Instrument,
    Price,
    VirtualCashEvent,
    VirtualCorporateAction,
    VirtualOrder,
    VirtualPortfolio,
    VirtualPortfolioSnapshot,
    VirtualPosition,
    VirtualWatchlistEntry,
)

MONEY = Decimal("0.01")
PRICE_QUANTUM = Decimal("0.000000000001")
QUANTITY_QUANTUM = Decimal("0.000000000000000001")
HUNDRED = Decimal("100")
BASIS_POINTS = Decimal("10000")
MAX_EQUITY_PRICE_AGE = timedelta(minutes=20)
MAX_CRYPTO_PRICE_AGE = timedelta(minutes=5)
TRADABLE_TYPES = {
    Instrument.Type.STOCK,
    Instrument.Type.ETF,
    Instrument.Type.FUND,
    Instrument.Type.BOND,
    Instrument.Type.CRYPTO,
    Instrument.Type.COMMODITY,
    Instrument.Type.OTHER,
}


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def price_value(value):
    return Decimal(value).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def quantity_value(value):
    return Decimal(value).quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def default_fractional_permission(instrument):
    return instrument.instrument_type == Instrument.Type.CRYPTO


def instrument_is_accessible(portfolio, instrument):
    return instrument.owner_id in {None, portfolio.user_id}


def latest_execution_price(instrument, *, as_of):
    return (
        Price.objects.filter(
            instrument=instrument,
            observed_at__lte=as_of,
            close_price__gt=0,
        )
        .exclude(quality=Price.Quality.ERROR)
        .order_by("-observed_at", "-collected_at", "-pk")
        .first()
    )


def _market_is_open(instrument, price, as_of):
    maximum_age = (
        MAX_CRYPTO_PRICE_AGE
        if instrument.instrument_type == Instrument.Type.CRYPTO
        else MAX_EQUITY_PRICE_AGE
    )
    if as_of - price.observed_at > maximum_age:
        return False, "Le dernier cours disponible est trop ancien."
    if instrument.instrument_type == Instrument.Type.CRYPTO:
        return True, ""
    if price.market_state != Price.MarketState.REGULAR:
        return False, "Le marché n'est pas en séance régulière."
    return True, ""


def _execution_unit_price(portfolio, order, stored_price):
    impact_bps = portfolio.spread_bps / Decimal("2") + portfolio.slippage_bps
    if order.side == VirtualOrder.Side.BUY:
        multiplier = Decimal("1") + impact_bps / BASIS_POINTS
    else:
        multiplier = Decimal("1") - impact_bps / BASIS_POINTS
    if multiplier <= 0:
        raise ValueError("Le spread et le slippage rendent le prix invalide.")
    return price_value(stored_price.close_price * multiplier)


def _fees(portfolio, gross_amount):
    return money(
        portfolio.fixed_fee
        + gross_amount * portfolio.proportional_fee_rate / HUNDRED
    )


def initialize_virtual_portfolio(portfolio, *, occurred_at=None, event_type=None):
    """Create the initial immutable cash event for a freshly saved portfolio."""
    timestamp = occurred_at or timezone.now()
    kind = event_type or VirtualCashEvent.Type.INITIAL
    return VirtualCashEvent.objects.create(
        portfolio=portfolio,
        event_type=kind,
        amount=money(portfolio.cash_balance),
        balance_after=money(portfolio.cash_balance),
        label="Capital virtuel de départ",
        occurred_at=timestamp,
    )


@transaction.atomic
def add_to_virtual_watchlist(portfolio, instrument, *, allow_fractional=None):
    if not instrument_is_accessible(portfolio, instrument):
        raise PermissionError("Instrument inaccessible pour ce portefeuille.")
    fractional = (
        default_fractional_permission(instrument)
        if allow_fractional is None
        else bool(allow_fractional)
    )
    entry, created = VirtualWatchlistEntry.objects.get_or_create(
        portfolio=portfolio,
        instrument=instrument,
        defaults={"allow_fractional": fractional},
    )
    if not created and entry.allow_fractional != fractional:
        entry.allow_fractional = fractional
        entry.full_clean()
        entry.save(update_fields=["allow_fractional"])
    return entry


def _validate_order_request(portfolio, instrument, quantity):
    if portfolio.archived:
        raise ValueError("Un portefeuille archivé ne peut plus recevoir d'ordre.")
    if not instrument_is_accessible(portfolio, instrument):
        raise PermissionError("Instrument inaccessible pour ce portefeuille.")
    if instrument.instrument_type not in TRADABLE_TYPES:
        raise ValueError("Ce type d'instrument n'est pas négociable virtuellement.")
    watch_entry = VirtualWatchlistEntry.objects.filter(
        portfolio=portfolio,
        instrument=instrument,
    ).first()
    if watch_entry is None:
        raise ValueError("Ajoutez d'abord l'instrument à la watchlist.")
    normalized_quantity = quantity_value(quantity)
    if normalized_quantity <= 0:
        raise ValueError("La quantité doit être strictement positive.")
    if not watch_entry.allow_fractional and normalized_quantity != normalized_quantity.to_integral_value():
        raise ValueError("Cet instrument exige une quantité entière dans ce portefeuille.")
    return normalized_quantity


@transaction.atomic
def place_virtual_order(
    portfolio,
    instrument,
    *,
    side,
    order_type,
    quantity,
    limit_price=None,
    submitted_at=None,
):
    portfolio = VirtualPortfolio.objects.select_for_update().get(pk=portfolio.pk)
    normalized_quantity = _validate_order_request(portfolio, instrument, quantity)
    timestamp = submitted_at or timezone.now()
    order = VirtualOrder(
        portfolio=portfolio,
        instrument=instrument,
        side=side,
        order_type=order_type,
        quantity=normalized_quantity,
        limit_price=price_value(limit_price) if limit_price is not None else None,
        submitted_at=timestamp,
    )
    order.full_clean()
    order.save()
    execute_virtual_order(order, as_of=timestamp)
    order.refresh_from_db()
    return order


def _mark_order(order, status, message):
    order.status = status
    order.status_message = message
    order.save(update_fields=["status", "status_message", "updated_at"])
    return order


@transaction.atomic
def execute_virtual_order(order, *, as_of=None):
    now = as_of or timezone.now()
    order = (
        VirtualOrder.objects.select_for_update()
        .select_related("portfolio", "instrument")
        .get(pk=order.pk)
    )
    if order.status != VirtualOrder.Status.OPEN:
        return order
    portfolio = VirtualPortfolio.objects.select_for_update().get(pk=order.portfolio_id)
    if portfolio.archived:
        return _mark_order(order, VirtualOrder.Status.REJECTED, "Portefeuille archivé.")
    stored_price = latest_execution_price(order.instrument, as_of=now)
    if stored_price is None:
        return _mark_order(order, VirtualOrder.Status.OPEN, "Aucun cours antérieur disponible.")
    if stored_price.currency != portfolio.base_currency:
        return _mark_order(
            order,
            VirtualOrder.Status.REJECTED,
            "La devise du cours diffère de celle du portefeuille.",
        )
    market_open, reason = _market_is_open(order.instrument, stored_price, now)
    if not market_open:
        return _mark_order(order, VirtualOrder.Status.OPEN, reason)
    try:
        execution_price = _execution_unit_price(portfolio, order, stored_price)
    except ValueError as exc:
        return _mark_order(order, VirtualOrder.Status.REJECTED, str(exc))
    if order.order_type == VirtualOrder.OrderType.LIMIT:
        limit_crossed = (
            execution_price <= order.limit_price
            if order.side == VirtualOrder.Side.BUY
            else execution_price >= order.limit_price
        )
        if not limit_crossed:
            return _mark_order(order, VirtualOrder.Status.OPEN, "Cours limite non atteint.")

    gross = money(execution_price * order.quantity)
    fees = _fees(portfolio, gross)
    position = (
        VirtualPosition.objects.select_for_update()
        .filter(portfolio=portfolio, instrument=order.instrument)
        .first()
    )
    if order.side == VirtualOrder.Side.BUY:
        cash_effect = money(-(gross + fees))
        if portfolio.cash_balance + cash_effect < 0:
            return _mark_order(order, VirtualOrder.Status.REJECTED, "Cash virtuel insuffisant.")
        if position is None:
            position = VirtualPosition(
                portfolio=portfolio,
                instrument=order.instrument,
                quantity=Decimal("0"),
                average_unit_cost=Decimal("0"),
            )
        old_cost = position.quantity * position.average_unit_cost
        new_quantity = quantity_value(position.quantity + order.quantity)
        position.average_unit_cost = price_value((old_cost + gross + fees) / new_quantity)
        position.quantity = new_quantity
    else:
        if position is None or position.quantity < order.quantity:
            return _mark_order(order, VirtualOrder.Status.REJECTED, "Position virtuelle insuffisante.")
        cash_effect = money(gross - fees)
        cost_released = money(position.average_unit_cost * order.quantity)
        position.realized_gain = money(position.realized_gain + cash_effect - cost_released)
        position.quantity = quantity_value(position.quantity - order.quantity)
    position.full_clean()
    position.save()

    portfolio.cash_balance = money(portfolio.cash_balance + cash_effect)
    portfolio.full_clean()
    portfolio.save(update_fields=["cash_balance", "updated_at"])
    order.status = VirtualOrder.Status.EXECUTED
    order.executed_at = now
    order.execution_unit_price = execution_price
    order.gross_amount = gross
    order.fees = fees
    order.cash_effect = cash_effect
    order.price_observed_at = stored_price.observed_at
    order.price_source = stored_price.source
    order.price_is_delayed = stored_price.is_delayed
    order.price_market_state = stored_price.market_state
    order.status_message = "Exécuté sur un cours stocké, sans appel réseau."
    order.full_clean()
    order.save()
    VirtualCashEvent.objects.create(
        portfolio=portfolio,
        event_type=(
            VirtualCashEvent.Type.BUY
            if order.side == VirtualOrder.Side.BUY
            else VirtualCashEvent.Type.SELL
        ),
        amount=cash_effect,
        balance_after=portfolio.cash_balance,
        order=order,
        instrument=order.instrument,
        label=f"Ordre virtuel {order.get_side_display().lower()}",
        occurred_at=now,
    )
    create_virtual_snapshot(portfolio, as_of=now)
    return order


def process_open_virtual_orders(portfolio, *, as_of=None):
    results = []
    for order in VirtualOrder.objects.filter(
        portfolio=portfolio,
        status=VirtualOrder.Status.OPEN,
    ).order_by("submitted_at", "pk"):
        results.append(execute_virtual_order(order, as_of=as_of))
    return tuple(results)


@transaction.atomic
def cancel_virtual_order(order):
    order = VirtualOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != VirtualOrder.Status.OPEN:
        raise ValueError("Seul un ordre ouvert peut être annulé.")
    order.status = VirtualOrder.Status.CANCELLED
    order.status_message = "Annulé manuellement."
    order.save(update_fields=["status", "status_message", "updated_at"])
    return order


@dataclass(frozen=True)
class VirtualPositionValuation:
    position: VirtualPosition
    unit_price: Decimal | None
    price_observed_at: object | None
    price_source: str
    price_is_delayed: bool
    current_value: Decimal | None
    unrealized_gain: Decimal | None


@dataclass(frozen=True)
class VirtualPortfolioValuation:
    cash_value: Decimal
    positions_value: Decimal
    total_value: Decimal
    absolute_gain: Decimal
    return_percent: Decimal
    realized_gain: Decimal
    unrealized_gain: Decimal
    dividend_income: Decimal
    benchmark_value: Decimal | None
    has_missing_prices: bool
    has_delayed_prices: bool
    positions: tuple[VirtualPositionValuation, ...]


def _benchmark_value(portfolio, as_of):
    if not portfolio.benchmark_instrument_id:
        return None
    initial = latest_execution_price(portfolio.benchmark_instrument, as_of=portfolio.created_at)
    current = latest_execution_price(portfolio.benchmark_instrument, as_of=as_of)
    if (
        initial is None
        or current is None
        or initial.currency != portfolio.base_currency
        or current.currency != portfolio.base_currency
    ):
        return None
    return money(portfolio.initial_cash * current.close_price / initial.close_price)


def virtual_portfolio_valuation(portfolio, *, as_of=None):
    now = as_of or timezone.now()
    # Callers can keep an instance obtained before an order was executed. Read
    # the persisted cash and configuration so a valuation never uses stale ORM
    # state.
    portfolio = VirtualPortfolio.objects.select_related("benchmark_instrument").get(
        pk=portfolio.pk
    )
    position_values = []
    positions_total = Decimal("0")
    realized = Decimal("0")
    unrealized = Decimal("0")
    dividends = Decimal("0")
    missing = False
    delayed = False
    for position in portfolio.virtual_positions.select_related("instrument"):
        realized += position.realized_gain
        dividends += position.dividend_income
        # A fully sold position stays in the journal so its realized result and
        # dividends remain part of the portfolio's lifetime performance.
        if position.quantity <= 0:
            continue
        stored_price = latest_execution_price(position.instrument, as_of=now)
        if stored_price is None or stored_price.currency != portfolio.base_currency:
            missing = True
            position_values.append(
                VirtualPositionValuation(position, None, None, "", False, None, None)
            )
            continue
        current_value = money(position.quantity * stored_price.close_price)
        position_gain = money(
            current_value - position.quantity * position.average_unit_cost
        )
        positions_total += current_value
        unrealized += position_gain
        delayed = delayed or stored_price.is_delayed
        position_values.append(
            VirtualPositionValuation(
                position=position,
                unit_price=stored_price.close_price,
                price_observed_at=stored_price.observed_at,
                price_source=stored_price.source,
                price_is_delayed=stored_price.is_delayed,
                current_value=current_value,
                unrealized_gain=position_gain,
            )
        )
    cash = money(portfolio.cash_balance)
    positions_total = money(positions_total)
    total = money(cash + positions_total)
    absolute = money(total - portfolio.initial_cash)
    return_percent = (
        (absolute / portfolio.initial_cash * HUNDRED).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        if portfolio.initial_cash
        else Decimal("0")
    )
    return VirtualPortfolioValuation(
        cash_value=cash,
        positions_value=positions_total,
        total_value=total,
        absolute_gain=absolute,
        return_percent=return_percent,
        realized_gain=money(realized),
        unrealized_gain=money(unrealized),
        dividend_income=money(dividends),
        benchmark_value=_benchmark_value(portfolio, now),
        has_missing_prices=missing,
        has_delayed_prices=delayed,
        positions=tuple(position_values),
    )


def create_virtual_snapshot(portfolio, *, as_of=None):
    observed_at = as_of or timezone.now()
    valuation = virtual_portfolio_valuation(portfolio, as_of=observed_at)
    return VirtualPortfolioSnapshot.objects.create(
        portfolio=portfolio,
        observed_at=observed_at,
        cash_value=valuation.cash_value,
        positions_value=valuation.positions_value,
        total_value=valuation.total_value,
        realized_gain=valuation.realized_gain,
        unrealized_gain=valuation.unrealized_gain,
        dividend_income=valuation.dividend_income,
        benchmark_value=valuation.benchmark_value,
        has_missing_prices=valuation.has_missing_prices,
        has_delayed_prices=valuation.has_delayed_prices,
    )


@transaction.atomic
def apply_virtual_corporate_action(action, *, as_of=None):
    now = as_of or timezone.now()
    action = (
        VirtualCorporateAction.objects.select_for_update()
        .select_related("portfolio", "instrument")
        .get(pk=action.pk)
    )
    if action.status != VirtualCorporateAction.Status.PENDING:
        return action
    if action.effective_at > now:
        action.status_message = "Événement futur, non appliqué."
        action.save(update_fields=["status_message"])
        return action
    portfolio = VirtualPortfolio.objects.select_for_update().get(pk=action.portfolio_id)
    position = (
        VirtualPosition.objects.select_for_update()
        .filter(portfolio=portfolio, instrument=action.instrument, quantity__gt=0)
        .first()
    )
    if position is None:
        action.status = VirtualCorporateAction.Status.REJECTED
        action.status_message = "Aucune position virtuelle à la date d'application."
        action.save(update_fields=["status", "status_message"])
        return action
    if action.action_type == VirtualCorporateAction.Type.DIVIDEND:
        amount = money(position.quantity * action.dividend_per_unit)
        portfolio.cash_balance = money(portfolio.cash_balance + amount)
        portfolio.save(update_fields=["cash_balance", "updated_at"])
        position.dividend_income = money(position.dividend_income + amount)
        position.save(update_fields=["dividend_income", "updated_at"])
        VirtualCashEvent.objects.create(
            portfolio=portfolio,
            event_type=VirtualCashEvent.Type.DIVIDEND,
            amount=amount,
            balance_after=portfolio.cash_balance,
            instrument=action.instrument,
            label="Dividende virtuel",
            occurred_at=now,
        )
    else:
        position.quantity = quantity_value(position.quantity * action.split_ratio)
        position.average_unit_cost = price_value(
            position.average_unit_cost / action.split_ratio
        )
        position.full_clean()
        position.save(update_fields=["quantity", "average_unit_cost", "updated_at"])
        for order in VirtualOrder.objects.select_for_update().filter(
            portfolio=portfolio,
            instrument=action.instrument,
            status=VirtualOrder.Status.OPEN,
        ):
            order.quantity = quantity_value(order.quantity * action.split_ratio)
            if order.limit_price is not None:
                order.limit_price = price_value(order.limit_price / action.split_ratio)
            order.full_clean()
            order.save(update_fields=["quantity", "limit_price", "updated_at"])
    action.status = VirtualCorporateAction.Status.APPLIED
    action.status_message = "Événement appliqué au registre virtuel."
    action.applied_at = now
    action.save(update_fields=["status", "status_message", "applied_at"])
    create_virtual_snapshot(portfolio, as_of=now)
    return action


@transaction.atomic
def reset_virtual_portfolio(portfolio):
    portfolio = VirtualPortfolio.objects.select_for_update().get(pk=portfolio.pk)
    portfolio.virtual_orders.all().delete()
    portfolio.corporate_actions.all().delete()
    portfolio.virtual_positions.all().delete()
    portfolio.performance_snapshots.all().delete()
    portfolio.cash_events.all().delete()
    portfolio.cash_balance = money(portfolio.initial_cash)
    portfolio.save(update_fields=["cash_balance", "updated_at"])
    initialize_virtual_portfolio(
        portfolio,
        event_type=VirtualCashEvent.Type.RESET,
    )
    return create_virtual_snapshot(portfolio)


@transaction.atomic
def clone_virtual_portfolio(source, *, name):
    source = (
        VirtualPortfolio.objects.select_for_update()
        .select_related("benchmark_instrument")
        .get(pk=source.pk)
    )
    now = timezone.now()
    valuation = virtual_portfolio_valuation(source, as_of=now)
    if valuation.total_value <= 0:
        raise ValueError("Un portefeuille sans valeur positive ne peut pas être cloné.")
    clone = VirtualPortfolio(
        user=source.user,
        name=name.strip(),
        base_currency=source.base_currency,
        initial_cash=valuation.total_value,
        cash_balance=valuation.cash_value,
        benchmark_instrument=source.benchmark_instrument,
        proportional_fee_rate=source.proportional_fee_rate,
        fixed_fee=source.fixed_fee,
        spread_bps=source.spread_bps,
        slippage_bps=source.slippage_bps,
    )
    clone.full_clean()
    clone.save()
    initialize_virtual_portfolio(
        clone,
        occurred_at=now,
        event_type=VirtualCashEvent.Type.CLONE,
    )
    VirtualWatchlistEntry.objects.bulk_create(
        [
            VirtualWatchlistEntry(
                portfolio=clone,
                instrument=entry.instrument,
                allow_fractional=entry.allow_fractional,
            )
            for entry in source.watchlist_entries.select_related("instrument")
        ]
    )
    valuation_by_instrument = {
        item.position.instrument_id: item for item in valuation.positions
    }
    for position in source.virtual_positions.select_related("instrument").filter(
        quantity__gt=0
    ):
        current = valuation_by_instrument.get(position.instrument_id)
        average_cost = (
            current.unit_price
            if current is not None and current.unit_price is not None
            else position.average_unit_cost
        )
        VirtualPosition.objects.create(
            portfolio=clone,
            instrument=position.instrument,
            quantity=position.quantity,
            average_unit_cost=average_cost,
        )
    create_virtual_snapshot(clone, as_of=now)
    return clone


def searchable_virtual_instruments(user, query=""):
    instruments = Instrument.objects.filter(
        Q(owner=user) | Q(owner__isnull=True),
        status=Instrument.Status.ACTIVE,
    ).exclude(manual_reference__startswith="system:benchmark:")
    normalized = query.strip()
    if normalized:
        instruments = instruments.filter(
            Q(name__icontains=normalized)
            | Q(ticker__icontains=normalized)
            | Q(isin__icontains=normalized)
        )
    return instruments.order_by("name", "ticker")[:30]

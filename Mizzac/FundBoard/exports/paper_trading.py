"""JSON and Excel exports for one user-owned virtual portfolio."""

import json
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Font

SCHEMA_VERSION = "1.0"


def _value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    return value


def _safe_cell(value):
    normalized = _value(value)
    if isinstance(normalized, str) and normalized.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{normalized}"
    return normalized


def virtual_portfolio_payload(portfolio, valuation):
    position_values = {item.position.pk: item for item in valuation.positions}
    return {
        "schema_version": SCHEMA_VERSION,
        "resource": "virtual_portfolio",
        "portfolio": {
            "name": portfolio.name,
            "base_currency": portfolio.base_currency,
            "initial_cash": portfolio.initial_cash,
            "cash_balance": portfolio.cash_balance,
            "benchmark": (
                portfolio.benchmark_instrument.name
                if portfolio.benchmark_instrument_id
                else None
            ),
            "proportional_fee_rate": portfolio.proportional_fee_rate,
            "fixed_fee": portfolio.fixed_fee,
            "spread_bps": portfolio.spread_bps,
            "slippage_bps": portfolio.slippage_bps,
            "created_at": portfolio.created_at,
        },
        "valuation": {
            "cash_value": valuation.cash_value,
            "positions_value": valuation.positions_value,
            "total_value": valuation.total_value,
            "absolute_gain": valuation.absolute_gain,
            "return_percent": valuation.return_percent,
            "realized_gain": valuation.realized_gain,
            "unrealized_gain": valuation.unrealized_gain,
            "dividend_income": valuation.dividend_income,
            "benchmark_value": valuation.benchmark_value,
            "has_missing_prices": valuation.has_missing_prices,
            "has_delayed_prices": valuation.has_delayed_prices,
        },
        "watchlist": [
            {
                "instrument": item.instrument.name,
                "ticker": item.instrument.ticker,
                "isin": item.instrument.isin,
                "allow_fractional": item.allow_fractional,
            }
            for item in portfolio.watchlist_entries.select_related("instrument")
        ],
        "positions": [
            {
                "instrument": item.instrument.name,
                "ticker": item.instrument.ticker,
                "quantity": item.quantity,
                "average_unit_cost": item.average_unit_cost,
                "realized_gain": item.realized_gain,
                "dividend_income": item.dividend_income,
                "current_unit_price": (
                    position_values[item.pk].unit_price
                    if item.pk in position_values
                    else None
                ),
                "current_value": (
                    position_values[item.pk].current_value
                    if item.pk in position_values
                    else None
                ),
                "unrealized_gain": (
                    position_values[item.pk].unrealized_gain
                    if item.pk in position_values
                    else None
                ),
            }
            for item in portfolio.virtual_positions.select_related("instrument")
        ],
        "orders": [
            {
                "client_order_id": item.client_order_id,
                "instrument": item.instrument.name,
                "ticker": item.instrument.ticker,
                "side": item.side,
                "order_type": item.order_type,
                "quantity": item.quantity,
                "limit_price": item.limit_price,
                "status": item.status,
                "submitted_at": item.submitted_at,
                "executed_at": item.executed_at,
                "execution_unit_price": item.execution_unit_price,
                "gross_amount": item.gross_amount,
                "fees": item.fees,
                "cash_effect": item.cash_effect,
                "price_observed_at": item.price_observed_at,
                "price_source": item.price_source,
                "price_is_delayed": item.price_is_delayed,
                "price_market_state": item.price_market_state,
                "status_message": item.status_message,
            }
            for item in portfolio.virtual_orders.select_related("instrument").order_by(
                "submitted_at", "pk"
            )
        ],
        "cash_events": [
            {
                "event_type": item.event_type,
                "amount": item.amount,
                "balance_after": item.balance_after,
                "instrument": item.instrument.name if item.instrument_id else None,
                "label": item.label,
                "occurred_at": item.occurred_at,
            }
            for item in portfolio.cash_events.select_related("instrument").order_by(
                "occurred_at", "pk"
            )
        ],
        "corporate_actions": [
            {
                "reference": item.reference,
                "instrument": item.instrument.name,
                "action_type": item.action_type,
                "effective_at": item.effective_at,
                "dividend_per_unit": item.dividend_per_unit,
                "split_ratio": item.split_ratio,
                "status": item.status,
                "status_message": item.status_message,
                "applied_at": item.applied_at,
            }
            for item in portfolio.corporate_actions.select_related("instrument").order_by(
                "effective_at", "pk"
            )
        ],
        "snapshots": [
            {
                "observed_at": item.observed_at,
                "cash_value": item.cash_value,
                "positions_value": item.positions_value,
                "total_value": item.total_value,
                "realized_gain": item.realized_gain,
                "unrealized_gain": item.unrealized_gain,
                "dividend_income": item.dividend_income,
                "benchmark_value": item.benchmark_value,
                "has_missing_prices": item.has_missing_prices,
                "has_delayed_prices": item.has_delayed_prices,
            }
            for item in portfolio.performance_snapshots.all()
        ],
        "execution_policy": (
            "Cours local antérieur ou égal à l'exécution ; actions en séance REGULAR ; "
            "cryptomonnaies 24/7 ; aucun appel courtier ou ordre réel."
        ),
    }


def virtual_portfolio_json_bytes(portfolio, valuation):
    return json.dumps(
        _value(virtual_portfolio_payload(portfolio, valuation)),
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8")


def _append_mapping(sheet, mapping):
    sheet.append(["Champ", "Valeur"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for key, value in mapping.items():
        sheet.append([key, _safe_cell(value)])
    sheet.column_dimensions["A"].width = 36
    sheet.column_dimensions["B"].width = 30


def _append_rows(sheet, rows):
    if not rows:
        return
    columns = list(rows[0])
    sheet.append(columns)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([_safe_cell(row[column]) for column in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def virtual_portfolio_excel_bytes(portfolio, valuation):
    payload = virtual_portfolio_payload(portfolio, valuation)
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Portefeuille"
    _append_mapping(overview, {**payload["portfolio"], **payload["valuation"]})
    for title, key in (
        ("Watchlist", "watchlist"),
        ("Positions", "positions"),
        ("Ordres", "orders"),
        ("Cash", "cash_events"),
        ("Événements", "corporate_actions"),
        ("Performance", "snapshots"),
    ):
        _append_rows(workbook.create_sheet(title), payload[key])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()

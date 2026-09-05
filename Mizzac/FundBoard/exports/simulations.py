"""Deterministic JSON and Excel exports for saved simulation scenarios."""

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

SCHEMA_VERSION = "1.0"


def _serializable(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


def _safe_cell(value):
    value = _serializable(value)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _json_bytes(payload):
    return json.dumps(
        _serializable(payload),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def loan_payload(scenario, result):
    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_type": "fixed_rate_amortizing_loan",
        "scenario": {
            "name": scenario.name,
            "currency": scenario.currency,
            "principal": scenario.principal,
            "annual_rate": scenario.annual_rate,
            "calculation_mode": scenario.calculation_mode,
            "duration_months": scenario.duration_months,
            "target_payment": scenario.target_payment,
            "insurance_mode": scenario.insurance_mode,
            "insurance_value": scenario.insurance_value,
            "insurance_basis": scenario.insurance_basis,
            "initial_fees": scenario.initial_fees,
            "deferment_months": scenario.deferment_months,
            "deferment_type": scenario.deferment_type,
            "one_off_prepayment": scenario.one_off_prepayment,
            "one_off_prepayment_month": scenario.one_off_prepayment_month,
            "recurring_prepayment": scenario.recurring_prepayment,
            "recurring_prepayment_start_month": (
                scenario.recurring_prepayment_start_month
            ),
            "start_date": scenario.start_date,
        },
        "result": {
            "regular_payment": result.regular_payment,
            "duration_months": result.duration_months,
            "payoff_date": result.payoff_date,
            "total_interest": result.total_interest,
            "total_insurance": result.total_insurance,
            "initial_fees": result.initial_fees,
            "total_cost": result.total_cost,
            "total_paid": result.total_paid,
        },
        "schedule": [asdict(row) for row in result.schedule],
        "rounding": "ROUND_HALF_UP à 0,01 après chaque opération mensuelle",
    }


def compound_payload(scenario, result):
    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_type": "compound_interest",
        "scenario": {
            "name": scenario.name,
            "currency": scenario.currency,
            "initial_capital": scenario.initial_capital,
            "periodic_contribution": scenario.periodic_contribution,
            "contribution_frequency": scenario.contribution_frequency,
            "contribution_timing": scenario.contribution_timing,
            "duration_years": scenario.duration_years,
            "annual_return": scenario.annual_return,
            "annual_fees": scenario.annual_fees,
            "annual_inflation": scenario.annual_inflation,
            "tax_mode": scenario.tax_mode,
            "tax_rate": scenario.tax_rate,
            "start_date": scenario.start_date,
        },
        "result": {
            "gross_final_value": result.gross_final_value,
            "final_nominal_value": result.final_nominal_value,
            "final_real_value": result.final_real_value,
            "total_contributed": result.total_contributed,
            "gross_gains": result.gross_gains,
            "net_gains": result.net_gains,
            "estimated_fees": result.estimated_fees,
            "estimated_tax": result.estimated_tax,
        },
        "timeline": [asdict(row) for row in result.timeline],
        "rounding": "ROUND_HALF_UP à 0,01 après chaque opération mensuelle",
    }


def simulation_json_bytes(scenario, result, simulation_type):
    payload = (
        loan_payload(scenario, result)
        if simulation_type == "loan"
        else compound_payload(scenario, result)
    )
    return _json_bytes(payload)


def _append_mapping(worksheet, mapping):
    worksheet.append(["Champ", "Valeur"])
    worksheet["A1"].font = Font(bold=True)
    worksheet["B1"].font = Font(bold=True)
    for key, value in mapping.items():
        worksheet.append([key, _safe_cell(value)])
    worksheet.column_dimensions["A"].width = 38
    worksheet.column_dimensions["B"].width = 28


def _workbook_bytes(payload, detail_key):
    workbook = Workbook()
    assumptions_sheet = workbook.active
    assumptions_sheet.title = "Hypothèses"
    _append_mapping(assumptions_sheet, payload["scenario"])
    summary_sheet = workbook.create_sheet("Résultats")
    _append_mapping(summary_sheet, payload["result"])
    detail_sheet = workbook.create_sheet(
        "Amortissement" if detail_key == "schedule" else "Projection"
    )
    details = payload[detail_key]
    if details:
        columns = list(details[0])
        detail_sheet.append(columns)
        for cell in detail_sheet[1]:
            cell.font = Font(bold=True)
        for item in details:
            detail_sheet.append([_safe_cell(item[column]) for column in columns])
        detail_sheet.freeze_panes = "A2"
        detail_sheet.auto_filter.ref = detail_sheet.dimensions
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def simulation_excel_bytes(scenario, result, simulation_type):
    payload = (
        loan_payload(scenario, result)
        if simulation_type == "loan"
        else compound_payload(scenario, result)
    )
    detail_key = "schedule" if simulation_type == "loan" else "timeline"
    return _workbook_bytes(payload, detail_key)

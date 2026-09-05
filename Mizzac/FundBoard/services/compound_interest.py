"""Pure monthly compound-interest simulator with explicit simplified taxation."""

import calendar
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MONEY = Decimal("0.01")
HUNDRED = Decimal("100")
MONTHS_PER_YEAR = Decimal("12")
MAX_YEARS = 100
FREQUENCY_MONTHS = {
    "MONTHLY": 1,
    "QUARTERLY": 3,
    "SEMIANNUAL": 6,
    "ANNUAL": 12,
}


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class CompoundInterestAssumptions:
    initial_capital: Decimal
    periodic_contribution: Decimal
    contribution_frequency: str
    contribution_timing: str
    duration_years: int
    annual_return: Decimal
    annual_fees: Decimal
    annual_inflation: Decimal
    tax_mode: str
    tax_rate: Decimal
    start_date: date


@dataclass(frozen=True)
class CompoundInterestRow:
    month: int
    period_date: date
    contribution: Decimal
    gross_return: Decimal
    fees: Decimal
    tax: Decimal
    closing_value: Decimal
    real_value: Decimal


@dataclass(frozen=True)
class CompoundInterestResult:
    gross_final_value: Decimal
    final_nominal_value: Decimal
    final_real_value: Decimal
    total_contributed: Decimal
    gross_gains: Decimal
    net_gains: Decimal
    estimated_fees: Decimal
    estimated_tax: Decimal
    timeline: tuple[CompoundInterestRow, ...]


def compound_assumptions_from_scenario(scenario):
    """Adapt a scenario-like object without importing Django or its models."""
    return CompoundInterestAssumptions(
        initial_capital=scenario.initial_capital,
        periodic_contribution=scenario.periodic_contribution,
        contribution_frequency=scenario.contribution_frequency,
        contribution_timing=scenario.contribution_timing,
        duration_years=scenario.duration_years,
        annual_return=scenario.annual_return,
        annual_fees=scenario.annual_fees,
        annual_inflation=scenario.annual_inflation,
        tax_mode=scenario.tax_mode,
        tax_rate=scenario.tax_rate,
        start_date=scenario.start_date,
    )


def _validate(assumptions):
    if assumptions.initial_capital < 0 or assumptions.periodic_contribution < 0:
        raise ValueError("Le capital et les versements ne peuvent pas être négatifs.")
    if money(assumptions.initial_capital) == 0 and money(assumptions.periodic_contribution) == 0:
        raise ValueError("Un capital initial ou un versement d'au moins 0,01 est nécessaire.")
    if assumptions.contribution_frequency not in FREQUENCY_MONTHS:
        raise ValueError("La fréquence des versements est invalide.")
    if assumptions.contribution_timing not in {"BEGIN", "END"}:
        raise ValueError("Le calendrier des versements est invalide.")
    if not 1 <= assumptions.duration_years <= MAX_YEARS:
        raise ValueError("La durée doit être comprise entre 1 et 100 ans.")
    if assumptions.annual_return <= -HUNDRED:
        raise ValueError("Le rendement doit être supérieur à -100 %.")
    if assumptions.annual_fees < 0 or assumptions.annual_fees > HUNDRED:
        raise ValueError("Les frais doivent être compris entre 0 et 100 %.")
    if assumptions.annual_inflation < 0:
        raise ValueError("L'inflation ne peut pas être négative.")
    if assumptions.tax_mode not in {"NONE", "FINAL_GAINS"}:
        raise ValueError("Le mode fiscal est invalide.")
    if assumptions.tax_rate < 0 or assumptions.tax_rate > HUNDRED:
        raise ValueError("Le taux fiscal doit être compris entre 0 et 100 %.")


def _contribution_due(month, interval, timing):
    if timing == "BEGIN":
        return (month - 1) % interval == 0
    return month % interval == 0


def calculate_compound_interest(assumptions):
    _validate(assumptions)
    monthly_return = assumptions.annual_return / HUNDRED / MONTHS_PER_YEAR
    monthly_fee_rate = assumptions.annual_fees / HUNDRED / MONTHS_PER_YEAR
    monthly_inflation = assumptions.annual_inflation / HUNDRED / MONTHS_PER_YEAR
    interval = FREQUENCY_MONTHS[assumptions.contribution_frequency]
    months = assumptions.duration_years * 12
    balance = money(assumptions.initial_capital)
    total_contributed = balance
    total_fees = Decimal("0")
    inflation_index = Decimal("1")
    rows = []

    for month_number in range(1, months + 1):
        contribution = Decimal("0.00")
        due = _contribution_due(
            month_number,
            interval,
            assumptions.contribution_timing,
        )
        if due and assumptions.contribution_timing == "BEGIN":
            contribution = money(assumptions.periodic_contribution)
            balance = money(balance + contribution)
        gross_return = money(balance * monthly_return)
        balance = money(balance + gross_return)
        fees = money(max(balance, Decimal("0")) * monthly_fee_rate)
        balance = money(balance - fees)
        if due and assumptions.contribution_timing == "END":
            contribution = money(assumptions.periodic_contribution)
            balance = money(balance + contribution)
        total_contributed += contribution
        total_fees += fees
        inflation_index *= Decimal("1") + monthly_inflation
        real_value = money(balance / inflation_index)
        rows.append(
            CompoundInterestRow(
                month=month_number,
                period_date=add_months(assumptions.start_date, month_number),
                contribution=contribution,
                gross_return=gross_return,
                fees=fees,
                tax=Decimal("0.00"),
                closing_value=balance,
                real_value=real_value,
            )
        )

    gross_final = balance
    taxable_gain = max(Decimal("0"), gross_final - total_contributed)
    tax = (
        money(taxable_gain * assumptions.tax_rate / HUNDRED)
        if assumptions.tax_mode == "FINAL_GAINS"
        else Decimal("0.00")
    )
    final_nominal = money(gross_final - tax)
    final_real = money(final_nominal / inflation_index)
    rows[-1] = replace(
        rows[-1],
        tax=tax,
        closing_value=final_nominal,
        real_value=final_real,
    )
    total_contributed = money(total_contributed)
    return CompoundInterestResult(
        gross_final_value=gross_final,
        final_nominal_value=final_nominal,
        final_real_value=final_real,
        total_contributed=total_contributed,
        gross_gains=money(gross_final - total_contributed),
        net_gains=money(final_nominal - total_contributed),
        estimated_fees=money(total_fees),
        estimated_tax=tax,
        timeline=tuple(rows),
    )

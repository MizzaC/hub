"""Pure fixed-rate amortizing-loan simulator.

The engine deliberately knows nothing about Django. Monetary flows and balances
are rounded to cents after every monthly operation using ROUND_HALF_UP.
"""

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

MONEY = Decimal("0.01")
HUNDRED = Decimal("100")
MONTHS_PER_YEAR = Decimal("12")
MAX_MONTHS = 1200


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class LoanAssumptions:
    principal: Decimal
    annual_rate: Decimal
    calculation_mode: str
    duration_months: int | None
    target_payment: Decimal | None
    insurance_mode: str
    insurance_value: Decimal
    insurance_basis: str
    initial_fees: Decimal
    deferment_months: int
    deferment_type: str
    one_off_prepayment: Decimal
    one_off_prepayment_month: int | None
    recurring_prepayment: Decimal
    recurring_prepayment_start_month: int | None
    start_date: date


@dataclass(frozen=True)
class LoanScheduleRow:
    month: int
    payment_date: date
    opening_balance: Decimal
    scheduled_payment: Decimal
    principal_paid: Decimal
    interest: Decimal
    insurance: Decimal
    prepayment: Decimal
    total_payment: Decimal
    closing_balance: Decimal


@dataclass(frozen=True)
class LoanSimulationResult:
    regular_payment: Decimal
    duration_months: int
    payoff_date: date
    total_interest: Decimal
    total_insurance: Decimal
    initial_fees: Decimal
    total_cost: Decimal
    total_paid: Decimal
    schedule: tuple[LoanScheduleRow, ...]


def loan_assumptions_from_scenario(scenario):
    """Adapt a scenario-like object without importing Django or its models."""
    return LoanAssumptions(
        principal=scenario.principal,
        annual_rate=scenario.annual_rate,
        calculation_mode=scenario.calculation_mode,
        duration_months=scenario.duration_months,
        target_payment=scenario.target_payment,
        insurance_mode=scenario.insurance_mode,
        insurance_value=scenario.insurance_value,
        insurance_basis=scenario.insurance_basis,
        initial_fees=scenario.initial_fees,
        deferment_months=scenario.deferment_months,
        deferment_type=scenario.deferment_type,
        one_off_prepayment=scenario.one_off_prepayment,
        one_off_prepayment_month=scenario.one_off_prepayment_month,
        recurring_prepayment=scenario.recurring_prepayment,
        recurring_prepayment_start_month=scenario.recurring_prepayment_start_month,
        start_date=scenario.start_date,
    )


def _validate(assumptions):
    if assumptions.principal <= 0 or money(assumptions.principal) == 0:
        raise ValueError("Le capital doit être d'au moins 0,01.")
    if assumptions.annual_rate < 0:
        raise ValueError("Le taux nominal ne peut pas être négatif.")
    if assumptions.calculation_mode not in {"PAYMENT", "DURATION"}:
        raise ValueError("Le mode de calcul du prêt est invalide.")
    if assumptions.insurance_mode not in {"FIXED", "PERCENT"}:
        raise ValueError("Le mode d'assurance est invalide.")
    if assumptions.insurance_mode == "PERCENT" and assumptions.insurance_value > HUNDRED:
        raise ValueError("Le taux d'assurance doit être compris entre 0 et 100 %.")
    if assumptions.insurance_basis not in {"INITIAL", "OUTSTANDING"}:
        raise ValueError("L'assiette d'assurance est invalide.")
    if assumptions.deferment_type not in {"NONE", "PARTIAL", "TOTAL"}:
        raise ValueError("Le type de différé est invalide.")
    if assumptions.insurance_value < 0 or assumptions.initial_fees < 0:
        raise ValueError("L'assurance et les frais doivent être positifs.")
    if assumptions.deferment_months < 0 or assumptions.deferment_months >= MAX_MONTHS:
        raise ValueError("La durée du différé est invalide.")
    if assumptions.deferment_type == "NONE" and assumptions.deferment_months:
        raise ValueError("Un différé nul est requis lorsque le type vaut aucun.")
    if assumptions.calculation_mode == "PAYMENT":
        if not assumptions.duration_months or not 1 <= assumptions.duration_months <= MAX_MONTHS:
            raise ValueError("La durée du prêt est invalide.")
        if assumptions.deferment_months >= assumptions.duration_months:
            raise ValueError("Le différé doit être inférieur à la durée totale.")
    elif assumptions.target_payment is None or assumptions.target_payment <= 0:
        raise ValueError("La mensualité cible doit être strictement positive.")
    for amount, month, label in (
        (
            assumptions.one_off_prepayment,
            assumptions.one_off_prepayment_month,
            "remboursement ponctuel",
        ),
        (
            assumptions.recurring_prepayment,
            assumptions.recurring_prepayment_start_month,
            "remboursement récurrent",
        ),
    ):
        if amount < 0 or (amount > 0 and (month is None or month < 1)):
            raise ValueError(f"Le {label} est invalide.")


def _monthly_interest(balance, monthly_rate):
    return money(balance * monthly_rate)


def _balance_after_total_deferment(principal, monthly_rate, months):
    balance = money(principal)
    for _ in range(months):
        balance = money(balance + _monthly_interest(balance, monthly_rate))
    return balance


def _calculated_payment(principal, monthly_rate, months):
    if months <= 0:
        raise ValueError("Aucune période d'amortissement n'est disponible.")
    if monthly_rate == 0:
        return money(principal / months)
    with localcontext() as context:
        context.prec = 50
        factor = (Decimal("1") + monthly_rate) ** months
        return money(principal * monthly_rate * factor / (factor - Decimal("1")))


def _insurance(assumptions, opening_balance):
    if assumptions.insurance_mode == "FIXED":
        return money(assumptions.insurance_value)
    basis = assumptions.principal if assumptions.insurance_basis == "INITIAL" else opening_balance
    return money(basis * assumptions.insurance_value / HUNDRED / MONTHS_PER_YEAR)


def calculate_loan(assumptions):
    _validate(assumptions)
    monthly_rate = assumptions.annual_rate / HUNDRED / MONTHS_PER_YEAR
    repayment_principal = money(assumptions.principal)
    if assumptions.deferment_type == "TOTAL":
        repayment_principal = _balance_after_total_deferment(
            repayment_principal,
            monthly_rate,
            assumptions.deferment_months,
        )
    if assumptions.calculation_mode == "PAYMENT":
        amortizing_months = assumptions.duration_months - assumptions.deferment_months
        regular_payment = _calculated_payment(
            repayment_principal,
            monthly_rate,
            amortizing_months,
        )
        maximum_month = assumptions.duration_months
    else:
        regular_payment = money(assumptions.target_payment)
        first_interest = _monthly_interest(repayment_principal, monthly_rate)
        if regular_payment <= first_interest:
            raise ValueError("La mensualité cible ne couvre pas les intérêts du premier mois.")
        maximum_month = MAX_MONTHS

    balance = money(assumptions.principal)
    rows = []
    total_interest = Decimal("0")
    total_insurance = Decimal("0")
    for month_number in range(1, maximum_month + 1):
        opening = balance
        interest = _monthly_interest(opening, monthly_rate)
        insurance = _insurance(assumptions, opening)
        principal_paid = Decimal("0.00")
        scheduled_payment = Decimal("0.00")

        if month_number <= assumptions.deferment_months:
            if assumptions.deferment_type == "TOTAL":
                balance = money(opening + interest)
            else:
                scheduled_payment = interest
                balance = opening
        else:
            principal_component = regular_payment - interest
            if principal_component <= 0:
                raise ValueError("La mensualité ne permet pas d'amortir le capital.")
            if (
                assumptions.calculation_mode == "PAYMENT"
                and month_number == assumptions.duration_months
            ):
                principal_paid = opening
            else:
                principal_paid = min(opening, principal_component)
            scheduled_payment = money(interest + principal_paid)
            balance = money(opening - principal_paid)

        requested_prepayment = Decimal("0")
        if (
            assumptions.one_off_prepayment > 0
            and month_number == assumptions.one_off_prepayment_month
        ):
            requested_prepayment += assumptions.one_off_prepayment
        if (
            assumptions.recurring_prepayment > 0
            and month_number >= assumptions.recurring_prepayment_start_month
        ):
            requested_prepayment += assumptions.recurring_prepayment
        prepayment = money(min(balance, requested_prepayment))
        balance = money(balance - prepayment)
        total_payment = money(scheduled_payment + insurance + prepayment)
        rows.append(
            LoanScheduleRow(
                month=month_number,
                payment_date=add_months(assumptions.start_date, month_number),
                opening_balance=opening,
                scheduled_payment=scheduled_payment,
                principal_paid=money(principal_paid),
                interest=interest,
                insurance=insurance,
                prepayment=prepayment,
                total_payment=total_payment,
                closing_balance=balance,
            )
        )
        total_interest += interest
        total_insurance += insurance
        if balance == 0:
            break
    else:
        raise ValueError("Le prêt ne peut pas être remboursé dans la limite de 1 200 mois.")

    total_interest = money(total_interest)
    total_insurance = money(total_insurance)
    initial_fees = money(assumptions.initial_fees)
    total_cost = money(total_interest + total_insurance + initial_fees)
    return LoanSimulationResult(
        regular_payment=regular_payment,
        duration_months=len(rows),
        payoff_date=rows[-1].payment_date,
        total_interest=total_interest,
        total_insurance=total_insurance,
        initial_fees=initial_fees,
        total_cost=total_cost,
        total_paid=money(assumptions.principal + total_cost),
        schedule=tuple(rows),
    )

"""Validated history writes for phase 7 asset classes."""

from django.db import transaction

from FundBoard.models import (
    LoanBalanceSnapshot,
    PrivateEquityValuation,
    RealEstateValuation,
)


@transaction.atomic
def record_real_estate_valuation(property_asset, *, value, valuation_date, source):
    normalized_source = source.strip().lower()
    snapshot = RealEstateValuation.objects.filter(
        real_estate=property_asset,
        valuation_date=valuation_date,
        source=normalized_source,
    ).first()
    snapshot = snapshot or RealEstateValuation(
        real_estate=property_asset,
        valuation_date=valuation_date,
        source=normalized_source,
    )
    snapshot.value = value
    snapshot.full_clean()
    snapshot.save()
    if valuation_date >= property_asset.valuation_date:
        property_asset.estimated_value = value
        property_asset.valuation_date = valuation_date
        property_asset.valuation_source = normalized_source
        property_asset.full_clean()
        property_asset.save(
            update_fields=[
                "estimated_value",
                "valuation_date",
                "valuation_source",
                "updated_at",
            ]
        )
    return snapshot


@transaction.atomic
def record_loan_balance(loan, *, outstanding_principal, observed_on, source):
    normalized_source = source.strip().lower()
    snapshot = LoanBalanceSnapshot.objects.filter(
        loan=loan,
        observed_on=observed_on,
        source=normalized_source,
    ).first()
    snapshot = snapshot or LoanBalanceSnapshot(
        loan=loan,
        observed_on=observed_on,
        source=normalized_source,
    )
    snapshot.outstanding_principal = outstanding_principal
    snapshot.full_clean()
    snapshot.save()
    if observed_on >= loan.balance_date:
        loan.outstanding_principal = outstanding_principal
        loan.balance_date = observed_on
        loan.full_clean()
        loan.save(update_fields=["outstanding_principal", "balance_date", "updated_at"])
    return snapshot


@transaction.atomic
def record_private_equity_valuation(
    holding,
    *,
    net_asset_value,
    called_capital,
    distributions,
    valuation_date,
    source,
):
    normalized_source = source.strip().lower()
    snapshot = PrivateEquityValuation.objects.filter(
        holding=holding,
        valuation_date=valuation_date,
        source=normalized_source,
    ).first()
    snapshot = snapshot or PrivateEquityValuation(
        holding=holding,
        valuation_date=valuation_date,
        source=normalized_source,
    )
    snapshot.net_asset_value = net_asset_value
    snapshot.called_capital = called_capital
    snapshot.distributions = distributions
    snapshot.full_clean()
    snapshot.save()
    if valuation_date >= holding.valuation_date:
        holding.net_asset_value = net_asset_value
        holding.called_capital = called_capital
        holding.distributions = distributions
        holding.valuation_date = valuation_date
        holding.valuation_source = normalized_source
        holding.full_clean()
        holding.save(
            update_fields=[
                "net_asset_value",
                "called_capital",
                "distributions",
                "valuation_date",
                "valuation_source",
                "updated_at",
            ]
        )
    return snapshot

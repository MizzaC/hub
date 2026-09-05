"""Idempotent daily snapshots created from cached, complete valuations."""

from dataclasses import dataclass
from datetime import datetime, time

from django.utils import timezone

from FundBoard.models import MarketDataPreference, Snapshot

from .net_worth import build_portfolio_valuation


class IncompleteValuationError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("Le snapshot exige une valorisation complète.")


@dataclass(frozen=True)
class SnapshotResult:
    created: int
    existing: int
    observed_at: datetime


def _daily_instant(day=None):
    snapshot_day = day or timezone.localdate()
    return timezone.make_aware(datetime.combine(snapshot_day, time.min))


def create_daily_snapshots(user, *, day=None):
    preference, _ = MarketDataPreference.objects.get_or_create(user=user)
    valuation = build_portfolio_valuation(user, preference.reporting_currency)
    if not valuation.complete:
        raise IncompleteValuationError(valuation.issues)

    observed_at = _daily_instant(day)
    created = 0
    existing = 0
    allocation = {label: str(value) for label, value in valuation.allocation}

    for line in valuation.lines:
        if line.category == "LIABILITY" or not (line.account or line.position):
            continue
        scope = Snapshot.Scope.POSITION if line.position else Snapshot.Scope.ACCOUNT
        _, was_created = Snapshot.objects.get_or_create(
            user=user,
            scope=scope,
            account=line.account,
            position=line.position,
            observed_at=observed_at,
            source=Snapshot.Source.CALCULATED,
            defaults={
                "original_value": line.original_value,
                "original_currency": line.original_currency,
                "converted_value": line.converted_value,
                "converted_currency": line.converted_currency,
                "exchange_rate": line.rate.rate,
                "exchange_rate_date": line.rate.rate_date,
                "metadata": {"value_source": line.source, "fx_source": line.rate.source},
            },
        )
        created += int(was_created)
        existing += int(not was_created)

    _, was_created = Snapshot.objects.get_or_create(
        user=user,
        scope=Snapshot.Scope.NET_WORTH,
        observed_at=observed_at,
        source=Snapshot.Source.CALCULATED,
        defaults={
            "original_value": valuation.net_worth,
            "original_currency": valuation.currency,
            "converted_value": valuation.net_worth,
            "converted_currency": valuation.currency,
            "exchange_rate": 1,
            "exchange_rate_date": observed_at.date(),
            "metadata": {
                "assets": str(valuation.assets),
                "liabilities": str(valuation.liabilities),
                "cash": str(valuation.cash),
                "allocation": allocation,
            },
        },
    )
    created += int(was_created)
    existing += int(not was_created)
    return SnapshotResult(created, existing, observed_at)

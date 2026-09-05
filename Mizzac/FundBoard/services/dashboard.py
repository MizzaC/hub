"""Cached dashboard series and portfolio/benchmark performance."""

from dataclasses import dataclass
from decimal import Decimal

from FundBoard.models import Price, Snapshot, Transaction

from .fx import ExchangeRateUnavailable, convert_with_stored_rate
from .performance import PerformanceResult, modified_dietz
from .transactions import performance_flow_from_transaction


@dataclass(frozen=True)
class DashboardPerformance:
    portfolio: PerformanceResult | None
    benchmark_return: Decimal | None
    start_date: object | None
    end_date: object | None
    issue: str = ""

    @property
    def portfolio_percent(self):
        return self.portfolio.return_rate * Decimal("100") if self.portfolio else None

    @property
    def benchmark_percent(self):
        return self.benchmark_return * Decimal("100") if self.benchmark_return is not None else None


def net_worth_snapshots(user, currency, *, limit=366):
    queryset = Snapshot.objects.filter(
        user=user,
        scope=Snapshot.Scope.NET_WORTH,
        converted_currency=currency,
    ).order_by("-observed_at")[:limit]
    return list(reversed(list(queryset)))


def _converted_performance_flows(user, start_date, end_date, currency):
    flows = []
    transactions = Transaction.objects.filter(
        user=user,
        status=Transaction.Status.BOOKED,
        executed_at__date__gte=start_date,
        executed_at__date__lte=end_date,
    ).select_related("linked_transfer")
    for transaction in transactions:
        flow = performance_flow_from_transaction(transaction)
        if flow is None:
            continue
        amount, _ = convert_with_stored_rate(
            flow.amount,
            transaction.currency,
            currency,
            on_date=flow.occurred_on,
        )
        flows.append(type(flow)(amount, flow.occurred_on, flow.kind))
    return flows


def build_dashboard_performance(user, preference, snapshots):
    if len(snapshots) < 2:
        return DashboardPerformance(None, None, None, None, "Deux snapshots sont nécessaires.")
    first = snapshots[0]
    last = snapshots[-1]
    start_date = first.observed_at.date()
    end_date = last.observed_at.date()
    if start_date == end_date:
        return DashboardPerformance(
            None,
            None,
            start_date,
            end_date,
            "Deux journées de snapshots sont nécessaires.",
        )
    try:
        flows = _converted_performance_flows(
            user,
            start_date,
            end_date,
            preference.reporting_currency,
        )
        portfolio = modified_dietz(
            first.converted_value,
            last.converted_value,
            start_date,
            end_date,
            flows,
        )
    except (ExchangeRateUnavailable, ValueError) as exc:
        return DashboardPerformance(None, None, start_date, end_date, str(exc))

    benchmark_return = None
    if preference.benchmark_instrument_id:
        prices = Price.objects.filter(
            instrument=preference.benchmark_instrument,
            observed_at__date__gte=start_date,
            observed_at__date__lte=end_date,
        ).order_by("observed_at")
        first_price = prices.first()
        last_price = prices.last()
        if first_price and last_price and first_price.pk != last_price.pk:
            benchmark_return = (
                last_price.close_price / first_price.close_price - Decimal("1")
            )
    return DashboardPerformance(
        portfolio,
        benchmark_return,
        start_date,
        end_date,
    )

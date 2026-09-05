from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from FundBoard.services.performance import FlowKind, PerformanceFlow, modified_dietz
from FundBoard.services.transactions import performance_flow_from_transaction


class PerformanceServiceTests(SimpleTestCase):
    def test_modified_dietz_weights_external_contribution(self):
        result = modified_dietz(
            Decimal("1000"),
            Decimal("1200"),
            date(2026, 1, 1),
            date(2026, 1, 31),
            [PerformanceFlow(Decimal("100"), date(2026, 1, 16), FlowKind.EXTERNAL)],
        )

        self.assertEqual(result.absolute_gain, Decimal("100.00000000"))
        self.assertEqual(result.external_flows, Decimal("100.00000000"))
        self.assertEqual(result.return_rate, Decimal("0.09523810"))

    def test_result_separates_income_costs_fx_and_market(self):
        flows = [
            PerformanceFlow(Decimal("20"), date(2026, 1, 10), FlowKind.INCOME),
            PerformanceFlow(Decimal("-5"), date(2026, 1, 12), FlowKind.FEE),
            PerformanceFlow(Decimal("-3"), date(2026, 1, 13), FlowKind.TAX),
            PerformanceFlow(Decimal("10"), date(2026, 1, 20), FlowKind.FX),
        ]

        result = modified_dietz(
            Decimal("1000"),
            Decimal("1100"),
            date(2026, 1, 1),
            date(2026, 2, 1),
            flows,
        )

        self.assertEqual(result.absolute_gain, Decimal("100.00000000"))
        self.assertEqual(result.market_gain, Decimal("78.00000000"))
        self.assertEqual(result.income, Decimal("20.00000000"))
        self.assertEqual(result.fees, Decimal("-5.00000000"))
        self.assertEqual(result.taxes, Decimal("-3.00000000"))
        self.assertEqual(result.fx_effect, Decimal("10.00000000"))

    def test_internal_transfer_is_not_an_external_flow(self):
        transaction = SimpleNamespace(
            status="BOOKED",
            transaction_type="TRANSFER",
            is_internal_transfer=True,
            net_amount=Decimal("-100"),
            executed_at=datetime(2026, 1, 15, 12),
        )

        flow = performance_flow_from_transaction(transaction)

        self.assertEqual(flow.kind, FlowKind.INTERNAL)

    def test_buy_does_not_create_portfolio_level_cash_flow(self):
        transaction = SimpleNamespace(
            status="BOOKED",
            transaction_type="BUY",
            is_internal_transfer=False,
            net_amount=Decimal("-100"),
            executed_at=datetime(2026, 1, 15, 12),
        )

        self.assertIsNone(performance_flow_from_transaction(transaction))

    def test_flow_outside_period_is_rejected(self):
        flow = PerformanceFlow(Decimal("10"), date(2025, 12, 31), FlowKind.EXTERNAL)

        with self.assertRaises(ValueError):
            modified_dietz(
                Decimal("1000"),
                Decimal("1010"),
                date(2026, 1, 1),
                date(2026, 2, 1),
                [flow],
            )

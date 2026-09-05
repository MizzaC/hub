from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from FundBoard.models import (
    Loan,
    PrivateEquityHolding,
    RealEstate,
)
from FundBoard.services.asset_history import (
    record_loan_balance,
    record_private_equity_valuation,
    record_real_estate_valuation,
)
from FundBoard.services.assets import loan_metrics, private_equity_metrics, real_estate_metrics

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class AssetMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="asset-metrics")
        cls.loan = Loan.objects.create(
            user=cls.user,
            manual_reference="loan-metrics",
            name="Prêt métriques",
            currency="EUR",
            original_principal=Decimal("200000"),
            outstanding_principal=Decimal("100000"),
            balance_date=date(2026, 9, 5),
            nominal_rate=Decimal("1.5"),
            duration_months=240,
            start_date=date(2022, 1, 1),
            payment_amount=Decimal("900"),
            insurance_amount=Decimal("25"),
        )
        cls.property = RealEstate.objects.create(
            user=cls.user,
            linked_loan=cls.loan,
            manual_reference="property-metrics",
            name="Appartement métriques",
            property_type=RealEstate.Type.APARTMENT,
            currency="EUR",
            purchase_price=Decimal("200000"),
            purchase_costs=Decimal("20000"),
            renovation_costs=Decimal("10000"),
            estimated_value=Decimal("300000"),
            valuation_date=date(2026, 9, 5),
            ownership_share=Decimal("50"),
            monthly_rent=Decimal("1000"),
            monthly_charges=Decimal("100"),
            annual_property_tax=Decimal("1200"),
            annual_insurance=Decimal("300"),
            annual_other_costs=Decimal("500"),
            vacancy_rate=Decimal("10"),
        )
        cls.holding = PrivateEquityHolding.objects.create(
            user=cls.user,
            manual_reference="pe-metrics",
            name="Fonds métriques",
            company_or_fund="Fonds Exemple",
            currency="EUR",
            commitment=Decimal("100"),
            called_capital=Decimal("80"),
            distributions=Decimal("20"),
            net_asset_value=Decimal("100"),
            valuation_date=date(2026, 9, 5),
            ownership_share=Decimal("50"),
        )

    def test_real_estate_metrics_use_ownership_vacancy_and_costs(self):
        metrics = real_estate_metrics(self.property)

        self.assertEqual(metrics.gross_value, Decimal("150000.00000000"))
        self.assertEqual(metrics.acquisition_cost, Decimal("115000.00000000"))
        self.assertEqual(metrics.net_value, Decimal("50000.00000000"))
        self.assertEqual(metrics.unrealized_gain, Decimal("35000.00000000"))
        self.assertEqual(metrics.annual_gross_rent, Decimal("6000.00000000"))
        self.assertEqual(metrics.annual_vacancy_loss, Decimal("600.00000000"))
        self.assertEqual(metrics.annual_costs, Decimal("1600.00000000"))
        self.assertEqual(metrics.annual_net_income, Decimal("3800.00000000"))
        self.assertEqual(metrics.gross_yield_percent, Decimal("5.2174"))
        self.assertEqual(metrics.net_yield_percent, Decimal("3.3043"))

    def test_loan_and_private_equity_metrics_are_decimal(self):
        loan_result = loan_metrics(self.loan)
        holding_result = private_equity_metrics(self.holding)

        self.assertEqual(loan_result.progress_percent, Decimal("50.0000"))
        self.assertEqual(loan_result.annual_payment, Decimal("10800.00000000"))
        self.assertEqual(holding_result.unfunded_commitment, Decimal("10.00000000"))
        self.assertEqual(holding_result.dpi, Decimal("0.2500"))
        self.assertEqual(holding_result.rvpi, Decimal("1.2500"))
        self.assertEqual(holding_result.tvpi, Decimal("1.5000"))

    def test_private_equity_refuses_called_capital_above_commitment(self):
        self.holding.called_capital = Decimal("101")
        with self.assertRaises(ValidationError):
            self.holding.full_clean()


class AssetHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="asset-history")
        cls.loan = Loan.objects.create(
            user=cls.user,
            manual_reference="loan-history",
            name="Prêt historique",
            original_principal=Decimal("100000"),
            outstanding_principal=Decimal("80000"),
            balance_date=date(2026, 9, 5),
            nominal_rate=Decimal("2"),
            duration_months=120,
            start_date=date(2025, 1, 1),
        )
        cls.property = RealEstate.objects.create(
            user=cls.user,
            manual_reference="property-history",
            name="Bien historique",
            property_type=RealEstate.Type.HOUSE,
            purchase_price=Decimal("200000"),
            estimated_value=Decimal("250000"),
            valuation_date=date(2026, 9, 5),
        )
        cls.holding = PrivateEquityHolding.objects.create(
            user=cls.user,
            manual_reference="pe-history",
            name="PE historique",
            company_or_fund="Fonds",
            commitment=Decimal("100000"),
            called_capital=Decimal("50000"),
            distributions=Decimal("5000"),
            net_asset_value=Decimal("60000"),
            valuation_date=date(2026, 9, 5),
        )

    def test_older_observation_preserves_current_and_newer_updates_it(self):
        record_real_estate_valuation(
            self.property,
            value=Decimal("240000"),
            valuation_date=date(2026, 9, 1),
            source="Expert",
        )
        record_loan_balance(
            self.loan,
            outstanding_principal=Decimal("85000"),
            observed_on=date(2026, 9, 1),
            source="Banque",
        )
        record_private_equity_valuation(
            self.holding,
            net_asset_value=Decimal("55000"),
            called_capital=Decimal("50000"),
            distributions=Decimal("4000"),
            valuation_date=date(2026, 9, 1),
            source="Rapport",
        )
        self.property.refresh_from_db()
        self.loan.refresh_from_db()
        self.holding.refresh_from_db()
        self.assertEqual(self.property.estimated_value, Decimal("250000"))
        self.assertEqual(self.loan.outstanding_principal, Decimal("80000"))
        self.assertEqual(self.holding.net_asset_value, Decimal("60000"))

        record_real_estate_valuation(
            self.property,
            value=Decimal("260000"),
            valuation_date=date(2026, 9, 6),
            source="Expert",
        )
        record_loan_balance(
            self.loan,
            outstanding_principal=Decimal("79000"),
            observed_on=date(2026, 9, 6),
            source="Banque",
        )
        record_private_equity_valuation(
            self.holding,
            net_asset_value=Decimal("62000"),
            called_capital=Decimal("52000"),
            distributions=Decimal("6000"),
            valuation_date=date(2026, 9, 6),
            source="Rapport",
        )
        self.property.refresh_from_db()
        self.loan.refresh_from_db()
        self.holding.refresh_from_db()
        self.assertEqual(self.property.estimated_value, Decimal("260000"))
        self.assertEqual(self.loan.outstanding_principal, Decimal("79000"))
        self.assertEqual(self.holding.net_asset_value, Decimal("62000"))


class AssetViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(username="asset-alice")
        cls.bob = get_user_model().objects.create_user(username="asset-bob")
        cls.alice_loan = Loan.objects.create(
            user=cls.alice,
            manual_reference="alice-loan",
            name="Prêt Alice",
            original_principal=Decimal("100000"),
            outstanding_principal=Decimal("80000"),
            balance_date=date(2026, 9, 5),
            nominal_rate=Decimal("2"),
            duration_months=120,
            start_date=date(2025, 1, 1),
        )
        cls.bob_loan = Loan.objects.create(
            user=cls.bob,
            manual_reference="bob-loan",
            name="Prêt Bob privé",
            original_principal=Decimal("100000"),
            outstanding_principal=Decimal("80000"),
            balance_date=date(2026, 9, 5),
            nominal_rate=Decimal("2"),
            duration_months=120,
            start_date=date(2025, 1, 1),
        )
        cls.alice_property = RealEstate.objects.create(
            user=cls.alice,
            manual_reference="alice-property",
            name="Bien Alice",
            property_type=RealEstate.Type.APARTMENT,
            purchase_price=Decimal("200000"),
            estimated_value=Decimal("250000"),
            valuation_date=date(2026, 9, 5),
        )
        cls.bob_property = RealEstate.objects.create(
            user=cls.bob,
            manual_reference="bob-property",
            name="Bien Bob privé",
            property_type=RealEstate.Type.HOUSE,
            purchase_price=Decimal("200000"),
            estimated_value=Decimal("250000"),
            valuation_date=date(2026, 9, 5),
        )
        cls.alice_holding = PrivateEquityHolding.objects.create(
            user=cls.alice,
            manual_reference="alice-pe",
            name="PE Alice",
            company_or_fund="Fonds Alice",
            commitment=Decimal("100000"),
            called_capital=Decimal("50000"),
            distributions=Decimal("5000"),
            net_asset_value=Decimal("60000"),
            valuation_date=date(2026, 9, 5),
        )
        cls.bob_holding = PrivateEquityHolding.objects.create(
            user=cls.bob,
            manual_reference="bob-pe",
            name="PE Bob privé",
            company_or_fund="Fonds Bob",
            commitment=Decimal("100000"),
            called_capital=Decimal("50000"),
            distributions=Decimal("5000"),
            net_asset_value=Decimal("60000"),
            valuation_date=date(2026, 9, 5),
        )

    def setUp(self):
        self.client.force_login(self.alice)

    def test_detail_pages_enforce_ownership(self):
        cases = [
            ("fundboard:real_estate_detail", self.alice_property.pk, self.bob_property.pk),
            ("fundboard:loan_detail", self.alice_loan.pk, self.bob_loan.pk),
            ("fundboard:private_equity_detail", self.alice_holding.pk, self.bob_holding.pk),
        ]
        for route, own_pk, other_pk in cases:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route, args=[own_pk])).status_code, 200)
                self.assertEqual(self.client.get(reverse(route, args=[other_pk])).status_code, 404)

    def test_private_equity_list_is_private(self):
        response = self.client.get(reverse("fundboard:private_equity"))
        self.assertContains(response, "PE Alice")
        self.assertNotContains(response, "PE Bob privé")

    def test_history_modal_rejects_another_users_parent(self):
        response = self.client.get(
            reverse("fundboard:add_loan_balance", args=[self.bob_loan.pk]),
            **AJAX,
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_uses_central_apexcharts_with_safe_json(self):
        record_real_estate_valuation(
            self.alice_property,
            value=Decimal("255000"),
            valuation_date=date(2026, 9, 6),
            source="manual",
        )
        response = self.client.get(
            reverse("fundboard:real_estate_detail", args=[self.alice_property.pk])
        )
        content = response.content.decode()
        self.assertIn("MizzacCharts.mount", content)
        self.assertIn('id="real-estate-history-values"', content)
        self.assertNotIn("|safe", content)

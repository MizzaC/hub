import decimal
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import FundBoard.validators


class Migration(migrations.Migration):
    dependencies = [
        ("FundBoard", "0006_compoundinterestscenario_loansimulationscenario"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VirtualPortfolio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("base_currency", models.CharField(default="EUR", max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ("initial_cash", models.DecimalField(decimal_places=8, max_digits=30)),
                ("cash_balance", models.DecimalField(decimal_places=8, max_digits=30)),
                ("proportional_fee_rate", models.DecimalField(decimal_places=4, default=decimal.Decimal("0"), help_text="Pourcentage appliqué au montant brut de chaque ordre.", max_digits=7)),
                ("fixed_fee", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("spread_bps", models.DecimalField(decimal_places=4, default=decimal.Decimal("0"), max_digits=9)),
                ("slippage_bps", models.DecimalField(decimal_places=4, default=decimal.Decimal("0"), max_digits=9)),
                ("archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("benchmark_instrument", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="virtual_benchmark_portfolios", to="FundBoard.instrument")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="virtual_portfolios", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["archived", "name", "pk"],
                "indexes": [models.Index(fields=["user", "archived"], name="virtual_user_archived_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(initial_cash__gt=0), name="virtual_initial_cash_pos"),
                    models.CheckConstraint(condition=models.Q(cash_balance__gte=0), name="virtual_cash_nonnegative"),
                    models.CheckConstraint(condition=models.Q(proportional_fee_rate__gte=0, proportional_fee_rate__lte=100), name="virtual_fee_rate_valid"),
                    models.CheckConstraint(condition=models.Q(fixed_fee__gte=0), name="virtual_fixed_fee_pos"),
                    models.CheckConstraint(condition=models.Q(spread_bps__gte=0), name="virtual_spread_pos"),
                    models.CheckConstraint(condition=models.Q(slippage_bps__gte=0), name="virtual_slippage_pos"),
                ],
            },
        ),
        migrations.CreateModel(
            name="VirtualOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_order_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("side", models.CharField(choices=[("BUY", "Achat"), ("SELL", "Vente")], max_length=4)),
                ("order_type", models.CharField(choices=[("MARKET", "Au marché"), ("LIMIT", "À cours limité")], max_length=6)),
                ("quantity", models.DecimalField(decimal_places=18, max_digits=36)),
                ("limit_price", models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ("status", models.CharField(choices=[("OPEN", "Ouvert"), ("EXECUTED", "Exécuté"), ("CANCELLED", "Annulé"), ("REJECTED", "Rejeté")], default="OPEN", max_length=10)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("execution_unit_price", models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ("gross_amount", models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ("fees", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("cash_effect", models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ("price_observed_at", models.DateTimeField(blank=True, null=True)),
                ("price_source", models.CharField(blank=True, max_length=50)),
                ("price_is_delayed", models.BooleanField(default=False)),
                ("price_market_state", models.CharField(blank=True, max_length=10)),
                ("status_message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="virtual_orders", to="FundBoard.instrument")),
                ("portfolio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="virtual_orders", to="FundBoard.virtualportfolio")),
            ],
            options={
                "ordering": ["-submitted_at", "-pk"],
                "indexes": [models.Index(fields=["portfolio", "status", "submitted_at"], name="virtual_order_status_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(quantity__gt=0), name="virtual_order_qty_pos"),
                    models.CheckConstraint(condition=models.Q(limit_price__isnull=True) | models.Q(limit_price__gt=0), name="virtual_order_limit_pos"),
                    models.CheckConstraint(condition=models.Q(fees__gte=0), name="virtual_order_fees_pos"),
                ],
            },
        ),
        migrations.CreateModel(
            name="VirtualCorporateAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("action_type", models.CharField(choices=[("DIVIDEND", "Dividende"), ("SPLIT", "Division d'actions")], max_length=10)),
                ("effective_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("dividend_per_unit", models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ("split_ratio", models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ("status", models.CharField(choices=[("PENDING", "À appliquer"), ("APPLIED", "Appliqué"), ("REJECTED", "Rejeté")], default="PENDING", max_length=10)),
                ("status_message", models.CharField(blank=True, max_length=255)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="virtual_corporate_actions", to="FundBoard.instrument")),
                ("portfolio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="corporate_actions", to="FundBoard.virtualportfolio")),
            ],
            options={
                "ordering": ["-effective_at", "-pk"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(dividend_per_unit__isnull=True) | models.Q(dividend_per_unit__gt=0), name="virtual_dividend_pos"),
                    models.CheckConstraint(condition=models.Q(split_ratio__isnull=True) | models.Q(split_ratio__gt=0), name="virtual_split_pos"),
                ],
            },
        ),
        migrations.CreateModel(
            name="VirtualCashEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("INITIAL", "Capital initial"), ("BUY", "Achat"), ("SELL", "Vente"), ("DIVIDEND", "Dividende"), ("RESET", "Remise à zéro"), ("CLONE", "Clonage")], max_length=10)),
                ("amount", models.DecimalField(decimal_places=8, max_digits=30)),
                ("balance_after", models.DecimalField(decimal_places=8, max_digits=30)),
                ("label", models.CharField(blank=True, max_length=255)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("instrument", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="virtual_cash_events", to="FundBoard.instrument")),
                ("order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cash_event", to="FundBoard.virtualorder")),
                ("portfolio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cash_events", to="FundBoard.virtualportfolio")),
            ],
            options={
                "ordering": ["-occurred_at", "-pk"],
                "indexes": [models.Index(fields=["portfolio", "-occurred_at"], name="virtual_cash_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="VirtualPortfolioSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("cash_value", models.DecimalField(decimal_places=8, max_digits=30)),
                ("positions_value", models.DecimalField(decimal_places=8, max_digits=30)),
                ("total_value", models.DecimalField(decimal_places=8, max_digits=30)),
                ("realized_gain", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("unrealized_gain", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("dividend_income", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("benchmark_value", models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ("has_missing_prices", models.BooleanField(default=False)),
                ("has_delayed_prices", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("portfolio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_snapshots", to="FundBoard.virtualportfolio")),
            ],
            options={
                "ordering": ["observed_at", "pk"],
                "indexes": [models.Index(fields=["portfolio", "observed_at"], name="virtual_snapshot_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="VirtualPosition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=18, default=decimal.Decimal("0"), max_digits=36)),
                ("average_unit_cost", models.DecimalField(decimal_places=12, max_digits=30)),
                ("realized_gain", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("dividend_income", models.DecimalField(decimal_places=8, default=decimal.Decimal("0"), max_digits=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="virtual_positions", to="FundBoard.instrument")),
                ("portfolio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="virtual_positions", to="FundBoard.virtualportfolio")),
            ],
            options={
                "ordering": ["instrument__name", "pk"],
                "constraints": [
                    models.UniqueConstraint(fields=("portfolio", "instrument"), name="uniq_virtual_position_instrument"),
                    models.CheckConstraint(condition=models.Q(quantity__gte=0), name="virtual_position_qty_pos"),
                    models.CheckConstraint(condition=models.Q(average_unit_cost__gte=0), name="virtual_position_cost_pos"),
                ],
            },
        ),
        migrations.CreateModel(
            name="VirtualWatchlistEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("allow_fractional", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="virtual_watchlist_entries", to="FundBoard.instrument")),
                ("portfolio", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watchlist_entries", to="FundBoard.virtualportfolio")),
            ],
            options={
                "ordering": ["instrument__name", "pk"],
                "constraints": [models.UniqueConstraint(fields=("portfolio", "instrument"), name="uniq_virtual_watch_instrument")],
            },
        ),
    ]

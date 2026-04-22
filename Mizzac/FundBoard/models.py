from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, getcontext

from django.contrib.auth.models import User
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone

getcontext().prec = 28


ACCOUNT_CATEGORIES = [
    ("CURRENT", "Compte courant"),
    ("SAVINGS", "Livret / Epargne"),
    ("CTO", "Compte Titres Ordinaire"),
    ("PEA", "Plan d'Epargne en Actions"),
    ("CRYPTO", "Portefeuille Crypto"),
    ("OTHER", "Autre"),
]

TRANSACTION_TYPES = [
    ("OPENING", "Ouverture"),
    ("DEPOSIT", "Depot"),
    ("WITHDRAWAL", "Retrait"),
    ("BUY", "Achat"),
    ("SELL", "Vente"),
    ("TRANSFER", "Transfert"),
    ("CONVERSION", "Conversion"),
    ("STAKING", "Staking"),
]

ADJUSTMENT_TYPES = [
    ("ROUNDING", "Rounding"),
    ("FX_SLIPPAGE", "FX slippage"),
    ("SYSTEM_CORRECTION", "System correction"),
]

FREQUENCY_CHOICES = [
    ("DAILY", "Quotidien"),
    ("WEEKLY", "Hebdomadaire"),
    ("MONTHLY", "Mensuel"),
    ("YEARLY", "Annuel"),
    ("PERSONALIZED", "Personnalise"),
]

RULE_KINDS = [
    ("INCOME", "Revenu"),
    ("EXPENSE", "Depense"),
]

MONTH_DAYS = Decimal("30")


class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=ACCOUNT_CATEGORIES, default="CURRENT")
    base_currency = models.CharField(max_length=10, default="EUR")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compte"
        verbose_name_plural = "Comptes"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["user", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.get_category_display()} ({self.user.username})"


class Asset(models.Model):
    ASSET_TYPES = [
        ("STOCK", "Action"),
        ("CRYPTO", "Cryptomonnaie"),
        ("ETF", "ETF"),
        ("FOREX", "Forex"),
        ("BOND", "Obligation"),
        ("FIAT", "Monnaie fiduciaire"),
    ]

    name = models.CharField(max_length=255)
    ticker = models.CharField(max_length=20, unique=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    precision = models.IntegerField(default=8)
    sector = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["ticker"]

    def __str__(self) -> str:
        return f"{self.name} ({self.ticker})"


class PriceHistory(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    date = models.DateField()
    open = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    high = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    low = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    close = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    reference_currency = models.CharField(max_length=10, default="EUR")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "date"], name="fundboard_pricehistory_asset_date_uniq"),
        ]
        indexes = [
            models.Index(fields=["asset", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.asset.ticker} - {self.date}"


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trx_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    executed_at = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255, blank=True, null=True)
    external_reference = models.CharField(max_length=255, blank=True, null=True)

    integrity_delta = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    tolerance_applied = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    is_balanced = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["user", "-executed_at"]),
            models.Index(fields=["user", "trx_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_trx_type_display()} - {self.executed_at:%d/%m/%Y %H:%M}"


class Leg(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="legs")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="legs")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="legs")

    quantity = models.DecimalField(max_digits=30, decimal_places=12)
    unit_price_reference = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    value_reference = models.DecimalField(max_digits=30, decimal_places=12)
    reference_currency = models.CharField(max_length=10, default="EUR")

    is_fee = models.BooleanField(default=False)
    is_adjustment = models.BooleanField(default=False)
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPES, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["transaction"]),
            models.Index(fields=["account", "asset"]),
            models.Index(fields=["asset"]),
        ]
        constraints = [
            CheckConstraint(
                check=(
                    Q(is_adjustment=False, adjustment_type__isnull=True)
                    | Q(is_adjustment=True, adjustment_type__isnull=False)
                ),
                name="fundboard_leg_adjustment_type_consistency",
            ),
        ]

    def __str__(self) -> str:
        return f"Leg#{self.pk} tx={self.transaction_id} {self.asset.ticker} qty={self.quantity}"


class CashflowRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=RULE_KINDS)
    is_recurring = models.BooleanField(default=False)

    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    next_due = models.DateField()

    freq = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, null=True, blank=True)
    freq_custom = models.PositiveIntegerField(null=True, blank=True)

    default_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    tag = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_due"]
        indexes = [
            models.Index(fields=["user", "kind"]),
            models.Index(fields=["user", "next_due"]),
            models.Index(fields=["user", "is_recurring"]),
        ]
        constraints = [
            CheckConstraint(
                check=(
                    Q(is_recurring=False, freq__isnull=True, freq_custom__isnull=True)
                    | Q(is_recurring=True, freq__isnull=False)
                ),
                name="fundboard_cashflowrule_recurring_freq_consistency",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} - {self.name}"

    @staticmethod
    def _add_months(d: date, months: int) -> date:
        y = d.year + (d.month - 1 + months) // 12
        m = (d.month - 1 + months) % 12 + 1
        last_day = monthrange(y, m)[1]
        return date(y, m, min(d.day, last_day))

    @staticmethod
    def _add_years(d: date, years: int) -> date:
        try:
            return d.replace(year=d.year + years)
        except ValueError:
            return d.replace(month=2, day=28, year=d.year + years)

    def _period_days(self) -> Decimal | None:
        if not self.is_recurring:
            return None
        if self.freq == "DAILY":
            return Decimal("1")
        if self.freq == "WEEKLY":
            return Decimal("7")
        if self.freq == "MONTHLY":
            return MONTH_DAYS
        if self.freq == "YEARLY":
            return Decimal("365")
        if self.freq == "PERSONALIZED" and (self.freq_custom or 0) > 0:
            return Decimal(str(int(self.freq_custom)))
        return None

    def next_due_upcoming(self, today: date | None = None) -> date:
        if today is None:
            today = timezone.now().date()
        d = self.next_due or today

        if not self.is_recurring:
            return d

        if self.freq == "DAILY":
            while d < today:
                d += timedelta(days=1)
        elif self.freq == "WEEKLY":
            while d < today:
                d += timedelta(days=7)
        elif self.freq == "MONTHLY":
            while d < today:
                d = self._add_months(d, 1)
        elif self.freq == "YEARLY":
            while d < today:
                d = self._add_years(d, 1)
        elif self.freq == "PERSONALIZED" and (self.freq_custom or 0) > 0:
            while d < today:
                d += timedelta(days=int(self.freq_custom))
        return d

    def monthly_equivalent(self) -> Decimal:
        if not self.is_recurring:
            return Decimal("0")
        days = self._period_days()
        if not days or days == 0:
            return Decimal("0")
        return (self.amount or Decimal("0")) * (MONTH_DAYS / days)


class Holding(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=30, decimal_places=12, default=Decimal("0"))
    avg_cost_reference = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    reference_currency = models.CharField(max_length=10, default="EUR")
    last_computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["account__name", "asset__ticker"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account", "asset"],
                name="fundboard_holding_user_account_asset_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["user", "account", "asset"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.account.name} - {self.asset.ticker}: {self.quantity}"

    @property
    def cost_basis(self) -> Decimal:
        q = self.quantity or Decimal("0")
        c = self.avg_cost_reference or Decimal("0")
        return q * c

    @property
    def avg_cost(self) -> Decimal:
        return self.avg_cost_reference or Decimal("0")

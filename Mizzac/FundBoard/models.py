# FundBoard/models.py
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, getcontext

from django.db import models
from django.db.models import CheckConstraint, Q
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
# Global decimal context (keep default precision but avoid floats)
# ─────────────────────────────────────────────────────────────
# You can tune precision if needed for financial calcs
getcontext().prec = 28


# ─────────────────────────────────────────────────────────────
# Choices / constants
# ─────────────────────────────────────────────────────────────

ACCOUNT_CATEGORIES = [
    ('CURRENT',  'Compte courant'),
    ('SAVINGS',  'Livret / Épargne'),
    ('CTO',      'Compte Titres Ordinaire'),
    ('PEA',      'Plan d’Épargne en Actions'),
    ('CRYPTO',   'Portefeuille Crypto'),
    ('OTHER',    'Autre'),
]

TRANSACTION_TYPES = [
    ('DEPOSIT',    'Dépôt'),
    ('WITHDRAWAL', 'Retrait'),
    ('BUY',        'Achat'),
    ('SELL',       'Vente'),
    ('TRANSFER',   'Transfert'),
]

FREQUENCY_CHOICES = [
    ('DAILY',        'Quotidien'),
    ('WEEKLY',       'Hebdomadaire'),
    ('MONTHLY',      'Mensuel'),
    ('YEARLY',       'Annuel'),
    ('PERSONALIZED', 'Personnalisé'),
]

# Month normalization used for "monthly equivalent"
# We stick to a 30-day month for display KPIs (consistent & simple).
MONTH_DAYS = Decimal('30')


# ─────────────────────────────────────────────────────────────
# Accounts
# ─────────────────────────────────────────────────────────────

class Account(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    name     = models.CharField(max_length=255)
    category = models.CharField(max_length=12, choices=ACCOUNT_CATEGORIES, default='CURRENT')
    balance  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='EUR', editable=True)

    class Meta:
        verbose_name = "Compte"
        verbose_name_plural = "Comptes"
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'name']),
        ]

    def __str__(self) -> str:
        return f"{self.name} – {self.get_category_display()} ({self.user.username})"


# ─────────────────────────────────────────────────────────────
# Instruments / assets
# ─────────────────────────────────────────────────────────────

class Asset(models.Model):
    ASSET_TYPES = [
        ('STOCK',   'Action'),
        ('CRYPTO',  'Cryptomonnaie'),
        ('ETF',     'ETF'),
        ('FOREX',   'Forex'),
        ('BOND',    'Obligation'),
    ]
    name       = models.CharField(max_length=255)
    ticker     = models.CharField(max_length=20, unique=True)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES)
    sector     = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.ticker})"


class PriceHistory(models.Model):
    asset    = models.ForeignKey(Asset, on_delete=models.CASCADE)
    date     = models.DateField()
    open     = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    high     = models.DecimalField(max_digits=15, decimal_places=2)
    low      = models.DecimalField(max_digits=15, decimal_places=2)
    close    = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    volume   = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('asset', 'date')
        indexes = [
            models.Index(fields=['asset', 'date']),
        ]

    def __str__(self) -> str:
        return f"{self.asset.ticker} - {self.date}"


# ─────────────────────────────────────────────────────────────
# Transactions (ledger)
# ─────────────────────────────────────────────────────────────
# NOTE:
# - amount > 0 = inflow, amount < 0 = outflow
# - For investments, use BUY/SELL with optional asset & quantity/unit_price.
# - For daily-life expenses, prefer the Expense/Income models for UX & KPIs.

class Transaction(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    account     = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    asset       = models.ForeignKey(Asset,   on_delete=models.CASCADE, null=True, blank=True)

    amount      = models.DecimalField(max_digits=15, decimal_places=2)  # inflow > 0, outflow < 0
    quantity    = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    unit_price  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    date_trx    = models.DateTimeField(default=timezone.now)
    trx_type    = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    memo        = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-date_trx']
        indexes = [
            models.Index(fields=['user', '-date_trx']),
            models.Index(fields=['user', 'trx_type']),
        ]

    def __str__(self) -> str:
        return f"{self.get_trx_type_display()} - {self.amount} - {self.date_trx:%d/%m/%Y %H:%M}"


# ─────────────────────────────────────────────────────────────
# Expenses (unified: one-time OR recurring)
# ─────────────────────────────────────────────────────────────
# Design:
# - is_recurring=False → one-time expense at `next_due`.
# - is_recurring=True  → rolling schedule. `next_due` stores the last known due;
#   we provide helpers to roll it forward to "upcoming" and to iterate occurrences.

class Expense(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    is_recurring = models.BooleanField(default=False)

    name         = models.CharField(max_length=255)
    amount       = models.DecimalField(max_digits=15, decimal_places=2)  # positive magnitude

    # Recurrence
    freq         = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, null=True, blank=True)
    freq_custom  = models.PositiveIntegerField(null=True, blank=True, help_text="Nombre de jours si personnalisé")

    # For one-time = date; for recurring = known next due (will be rolled forward by helpers)
    next_due     = models.DateField()

    # Optional linking
    account      = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    tag          = models.CharField(max_length=50, blank=True, null=True)
    notes        = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['next_due']
        indexes = [
            models.Index(fields=['user', 'next_due']),
            models.Index(fields=['user', 'is_recurring']),
            models.Index(fields=['user', 'tag']),
        ]
        constraints = [
            # If recurring, freq must be set; if personalized, freq_custom > 0
            CheckConstraint(
                check=(
                    Q(is_recurring=False, freq__isnull=True, freq_custom__isnull=True)
                    |
                    Q(
                        is_recurring=True,
                        freq__isnull=False,
                    )
                ),
                name='expense_recurring_freq_consistency'
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.amount} €"

    # --------------------- date helpers ---------------------

    @staticmethod
    def _add_months(d: date, months: int) -> date:
        """Add N months while clamping to month-end if needed."""
        y = d.year + (d.month - 1 + months) // 12
        m = (d.month - 1 + months) % 12 + 1
        from calendar import monthrange
        last_day = monthrange(y, m)[1]
        day = min(d.day, last_day)
        return date(y, m, day)

    @staticmethod
    def _add_years(d: date, years: int) -> date:
        """Add N years; clamp Feb 29 to Feb 28 if needed."""
        try:
            return d.replace(year=d.year + years)
        except ValueError:
            return d.replace(month=2, day=28, year=d.year + years)

    def _period_days(self) -> Decimal | None:
        """Return the nominal number of days for this expense period (Decimal), or None if one-time."""
        if not self.is_recurring:
            return None
        if self.freq == 'DAILY':
            return Decimal('1')
        if self.freq == 'WEEKLY':
            return Decimal('7')
        if self.freq == 'MONTHLY':
            return MONTH_DAYS  # normalized to 30 days
        if self.freq == 'YEARLY':
            return Decimal('365')
        if self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
            return Decimal(str(int(self.freq_custom)))
        return None

    def next_due_upcoming(self, today: date | None = None) -> date:
        """
        Return the next due date at or after `today`.
        If recurring, rolls forward from stored `next_due` until it reaches today or beyond.
        """
        if today is None:
            today = timezone.now().date()
        d = self.next_due or today

        if not self.is_recurring:
            return d

        if self.freq == 'DAILY':
            while d < today:
                d += timedelta(days=1)
        elif self.freq == 'WEEKLY':
            while d < today:
                d += timedelta(days=7)
        elif self.freq == 'MONTHLY':
            while d < today:
                d = self._add_months(d, 1)
        elif self.freq == 'YEARLY':
            while d < today:
                d = self._add_years(d, 1)
        elif self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
            step = int(self.freq_custom)
            while d < today:
                d += timedelta(days=step)
        return d

    def iter_occurrences(self, start: date, end: date):
        """
        Yield all occurrence dates within [start, end] inclusive.
        For one-time: yields once if next_due in range.
        For recurring: roll forward to >= start then iterate until > end.
        """
        if start > end:
            return
        if not self.is_recurring:
            if self.next_due and start <= self.next_due <= end:
                yield self.next_due
            return

        # roll to first occurrence >= start
        d = self.next_due_upcoming(today=start)

        while d <= end:
            yield d
            if self.freq == 'DAILY':
                d += timedelta(days=1)
            elif self.freq == 'WEEKLY':
                d += timedelta(days=7)
            elif self.freq == 'MONTHLY':
                d = self._add_months(d, 1)
            elif self.freq == 'YEARLY':
                d = self._add_years(d, 1)
            elif self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
                d += timedelta(days=int(self.freq_custom))
            else:
                break  # invalid setting → stop

    # --------------------- KPI helpers ---------------------

    def monthly_equivalent(self) -> Decimal:
        """
        Return the monthly equivalent cost (Decimal).
        - For one-time, returns Decimal('0') because it should be summed directly in the month it happens.
        - For recurring, normalize to a 30-day month using period days.
        """
        if not self.is_recurring:
            return Decimal('0')
        days = self._period_days()
        if not days or days == 0:
            return Decimal('0')
        # amount * (30 / period_days)  — purely Decimal math
        return (self.amount or Decimal('0')) * (MONTH_DAYS / days)

    def as_signed_flow(self) -> Decimal:
        """Return the signed flow (expenses are outflows): negative amount for compatibility with net calculations."""
        amt = self.amount or Decimal('0')
        return -amt  # expenses reduce net


# ─────────────────────────────────────────────────────────────
# Incomes (unified: one-time OR recurring)
# ─────────────────────────────────────────────────────────────

class Income(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)

    is_recurring = models.BooleanField(default=False)
    name         = models.CharField(max_length=255)
    amount       = models.DecimalField(max_digits=15, decimal_places=2)  # positive magnitude

    # Recurrence (optional)
    freq         = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, null=True, blank=True)
    freq_custom  = models.PositiveIntegerField(null=True, blank=True)

    # For one-time = date; for recurring = last known next payday (rolled by helper)
    next_payday  = models.DateField()

    notes        = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['next_payday']
        indexes = [
            models.Index(fields=['user', 'next_payday']),
            models.Index(fields=['user', 'is_recurring']),
        ]
        constraints = [
            CheckConstraint(
                check=(
                    Q(is_recurring=False, freq__isnull=True, freq_custom__isnull=True)
                    |
                    Q(is_recurring=True,  freq__isnull=False)
                ),
                name='income_recurring_freq_consistency'
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.amount} €"

    # --------------------- date helpers (reuse logic) ---------------------

    @staticmethod
    def _add_months(d: date, months: int) -> date:
        y = d.year + (d.month - 1 + months) // 12
        m = (d.month - 1 + months) % 12 + 1
        from calendar import monthrange
        last_day = monthrange(y, m)[1]
        day = min(d.day, last_day)
        return date(y, m, day)

    @staticmethod
    def _add_years(d: date, years: int) -> date:
        try:
            return d.replace(year=d.year + years)
        except ValueError:
            return d.replace(month=2, day=28, year=d.year + years)

    def _period_days(self) -> Decimal | None:
        if not self.is_recurring:
            return None
        if self.freq == 'DAILY':
            return Decimal('1')
        if self.freq == 'WEEKLY':
            return Decimal('7')
        if self.freq == 'MONTHLY':
            return MONTH_DAYS
        if self.freq == 'YEARLY':
            return Decimal('365')
        if self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
            return Decimal(str(int(self.freq_custom)))
        return None

    def next_payday_upcoming(self, today: date | None = None) -> date:
        """Return the next payday at or after `today` (rolls forward if recurring)."""
        if today is None:
            today = timezone.now().date()
        d = self.next_payday or today

        if not self.is_recurring:
            return d

        if self.freq == 'DAILY':
            while d < today:
                d += timedelta(days=1)
        elif self.freq == 'WEEKLY':
            while d < today:
                d += timedelta(days=7)
        elif self.freq == 'MONTHLY':
            while d < today:
                d = self._add_months(d, 1)
        elif self.freq == 'YEARLY':
            while d < today:
                d = self._add_years(d, 1)
        elif self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
            step = int(self.freq_custom)
            while d < today:
                d += timedelta(days=step)
        return d

    def iter_occurrences(self, start: date, end: date):
        """Yield all paydays within [start, end] inclusive."""
        if start > end:
            return
        if not self.is_recurring:
            if self.next_payday and start <= self.next_payday <= end:
                yield self.next_payday
            return

        d = self.next_payday_upcoming(today=start)
        while d <= end:
            yield d
            if self.freq == 'DAILY':
                d += timedelta(days=1)
            elif self.freq == 'WEEKLY':
                d += timedelta(days=7)
            elif self.freq == 'MONTHLY':
                d = self._add_months(d, 1)
            elif self.freq == 'YEARLY':
                d = self._add_years(d, 1)
            elif self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
                d += timedelta(days=int(self.freq_custom))
            else:
                break

    def monthly_equivalent(self) -> Decimal:
        """Monthly equivalent income based on a 30-day normalized month (Decimal only)."""
        if not self.is_recurring:
            return Decimal('0')
        days = self._period_days()
        if not days or days == 0:
            return Decimal('0')
        return (self.amount or Decimal('0')) * (MONTH_DAYS / days)

    def as_signed_flow(self) -> Decimal:
        """Positive inflow for nets."""
        return self.amount or Decimal('0')


# ─────────────────────────────────────────────────────────────
# Holdings (positions) — updated from BUY/SELL transactions
# ─────────────────────────────────────────────────────────────

class Holding(models.Model):
    """Current position for a (user, account, asset) computed from BUY/SELL."""
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    account      = models.ForeignKey(Account, on_delete=models.CASCADE)
    asset        = models.ForeignKey(Asset, on_delete=models.CASCADE)
    quantity     = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    avg_cost     = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))  # per unit
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'account', 'asset')
        ordering = ['account__name', 'asset__ticker']
        indexes = [
            models.Index(fields=['user', 'account', 'asset']),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} – {self.account.name} – {self.asset.ticker}: {self.quantity}"

    @property
    def cost_basis(self) -> Decimal:
        """Total invested capital at average cost (without realized P&L)."""
        q = self.quantity or Decimal('0')
        c = self.avg_cost or Decimal('0')
        return q * c

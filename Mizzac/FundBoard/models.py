# FundBoard/models.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from calendar import monthrange
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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

    def __str__(self):
        return f"{self.name} – {self.get_category_display()} ({self.user.username})"


# ─────────────────────────────────────────────────────────────
# Instruments / assets (optionnel selon usage actuel)
# ─────────────────────────────────────────────────────────────

class Asset(models.Model):
    ASSET_TYPES = [
        ('STOCK',     'Action'),
        ('CRYPTO',    'Cryptomonnaie'),
        ('ETF',       'ETF'),
        ('FOREX',     'Forex'),
        ('BOND',      'Obligation'),
    ]
    name       = models.CharField(max_length=255)
    ticker     = models.CharField(max_length=20, unique=True)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES)
    sector     = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
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

    def __str__(self):
        return f"{self.asset.ticker} - {self.date}"


# ─────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────

class Transaction(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    account     = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    asset       = models.ForeignKey(Asset,   on_delete=models.CASCADE, null=True, blank=True)

    amount      = models.DecimalField(max_digits=15, decimal_places=2)           # +/- cash
    quantity    = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    unit_price  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    date_trx    = models.DateTimeField(default=timezone.now)
    trx_type    = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    memo        = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-date_trx']

    def __str__(self):
        return f"{self.get_trx_type_display()} - {self.amount} - {self.date_trx:%d/%m/%Y %H:%M}"


# ─────────────────────────────────────────────────────────────
# Expenses (unified: one-time OR recurring)
# ─────────────────────────────────────────────────────────────

class Expense(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    is_recurring = models.BooleanField(default=False)

    name         = models.CharField(max_length=255)
    amount       = models.DecimalField(max_digits=15, decimal_places=2)

    # Recurrence (optional if not recurring)
    freq         = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, null=True, blank=True)
    freq_custom  = models.PositiveIntegerField(null=True, blank=True, help_text="Nombre de jours si personnalisé")

    # For one-time = date; for recurring = prochaine échéance connue (roulera au prochain affichage)
    next_due     = models.DateField()

    # Optional linking
    account      = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    tag          = models.CharField(max_length=50, blank=True, null=True)
    notes        = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['next_due']

    def __str__(self):
        return f"{self.name} - {self.amount} €"

    # ──────────────── Helpers for next occurrence ────────────────

    @staticmethod
    def _add_months(d: date, months: int) -> date:
        """Add N months to a date, clamping to the last valid day."""
        y = d.year + (d.month - 1 + months) // 12
        m = (d.month - 1 + months) % 12 + 1
        last_day = monthrange(y, m)[1]
        day = min(d.day, last_day)
        return date(y, m, day)

    @staticmethod
    def _add_years(d: date, years: int) -> date:
        """Add N years to a date, handling Feb 29 to Feb 28."""
        try:
            return d.replace(year=d.year + years)
        except ValueError:
            # 29 Feb → 28 Feb
            return d.replace(month=2, day=28, year=d.year + years)

    def next_due_upcoming(self, today: date | None = None) -> date:
        """
        Return the next due date at or after `today`.
        - If not recurring → returns stored next_due (one-time)
        - If recurring and next_due < today → roll forward by the recurrence rule
        """
        if today is None:
            today = timezone.now().date()
        d = self.next_due or today

        if not self.is_recurring:
            return d

        # Choose step
        if self.freq == 'DAILY':
            step_days = 1
            while d < today:
                d += timedelta(days=step_days)
            return d

        if self.freq == 'WEEKLY':
            step_days = 7
            while d < today:
                d += timedelta(days=step_days)
            return d

        if self.freq == 'MONTHLY':
            while d < today:
                d = self._add_months(d, 1)
            return d

        if self.freq == 'YEARLY':
            while d < today:
                d = self._add_years(d, 1)
            return d

        if self.freq == 'PERSONALIZED' and (self.freq_custom or 0) > 0:
            step_days = int(self.freq_custom)
            while d < today:
                d += timedelta(days=step_days)
            return d

        # Fallback: if rule invalid, just return stored date
        return d


# ─────────────────────────────────────────────────────────────
# Incomes (kept as-is)
# ─────────────────────────────────────────────────────────────

class Income(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    name         = models.CharField(max_length=255)
    amount       = models.DecimalField(max_digits=15, decimal_places=2)

    freq         = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    freq_custom  = models.PositiveIntegerField(null=True, blank=True)
    next_payday  = models.DateField()

    notes        = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['next_payday']

    def __str__(self):
        return f"{self.name} - {self.amount} €"

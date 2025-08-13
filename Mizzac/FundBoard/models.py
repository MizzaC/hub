# FundBoard/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

# ════════════════════════════════════════════════════════════════
# ENUM / CHOICES (kept compatible with your current code)
# ════════════════════════════════════════════════════════════════
ACCOUNT_CATEGORIES = [
    ('CURRENT', 'Compte courant'),
    ('SAVINGS', 'Livret / Épargne'),
    ('CTO',     'Compte Titres Ordinaire'),
    ('PEA',     'Plan d’Épargne en Actions'),
    ('CRYPTO',  'Portefeuille Crypto'),
    ('OTHER',   'Autre'),
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

# ════════════════════════════════════════════════════════════════
# 1) Unified Account (unchanged)
# ════════════════════════════════════════════════════════════════
class Account(models.Model):
    user          = models.ForeignKey(User, on_delete=models.CASCADE)
    name          = models.CharField(max_length=255)
    category      = models.CharField(max_length=10, choices=ACCOUNT_CATEGORIES)
    balance       = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency      = models.CharField(max_length=10, default='EUR')
    api_service   = models.CharField(max_length=50, blank=True, null=True)
    api_connected = models.BooleanField(default=False)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} – {self.get_category_display()} ({self.user.username})"

# ════════════════════════════════════════════════════════════════
# 2) Assets & Price history (unchanged)
# ════════════════════════════════════════════════════════════════
class Asset(models.Model):
    ASSET_TYPES = [
        ('STOCK',     'Action'),
        ('CRYPTO',    'Cryptomonnaie'),
        ('ETF',       'ETF'),
        ('FOREX',     'Forex'),
        ('OBLIGATION','Obligation'),
    ]
    name        = models.CharField(max_length=255)
    ticker      = models.CharField(max_length=20, unique=True)
    type_asset  = models.CharField(max_length=10, choices=ASSET_TYPES)
    sector      = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.ticker})"

class PriceHistory(models.Model):
    asset       = models.ForeignKey(Asset, on_delete=models.CASCADE)
    date        = models.DateField()
    open_price  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    high_price  = models.DecimalField(max_digits=15, decimal_places=2)
    low_price   = models.DecimalField(max_digits=15, decimal_places=2)
    close_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    volume      = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('asset', 'date')

    def __str__(self):
        return f"{self.asset.ticker} – {self.date}"

# ════════════════════════════════════════════════════════════════
# 3) Transactions (FK → Account only)
# ════════════════════════════════════════════════════════════════
class Transaction(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    account      = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    asset        = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True)
    amount       = models.DecimalField(max_digits=15, decimal_places=2)
    quantity     = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    unit_price   = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date_trx     = models.DateTimeField(default=timezone.now)
    trx_type     = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    other_details= models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.get_trx_type_display()} – {self.amount} – {self.date_trx:%d/%m/%Y}"

# ════════════════════════════════════════════════════════════════
# 4) Watchlists (unchanged)
# ════════════════════════════════════════════════════════════════
class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class WatchAsset(models.Model):
    watchlist = models.ForeignKey(Watchlist, on_delete=models.CASCADE)
    asset     = models.ForeignKey(Asset, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.watchlist.name} – {self.asset.ticker}"

# ════════════════════════════════════════════════════════════════
# 5) Unified EXPENSE model (recurring or one-time)
# ────────────────────────────────────────────────────────────────
# Design:
# - One single model covers both cases.
# - is_recurring=True → frequency fields are used; next_due = next occurrence
# - is_recurring=False → single payment; next_due = expense date
# - Keep field names (freq/freq_custom/next_due) for compatibility with templates
# - Optional future fields: account, tag, notes
# ════════════════════════════════════════════════════════════════
class Expense(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    name        = models.CharField(max_length=255)
    amount      = models.DecimalField(max_digits=15, decimal_places=2)
    is_recurring= models.BooleanField(default=True)
    # Recurrence details (used only if is_recurring=True)
    freq        = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, null=True, blank=True)
    freq_custom = models.IntegerField(null=True, blank=True,
                                      help_text="If 'PERSONALIZED', number of days between payments.")
    # Date field used for both: next due date (recurring) or the single occurrence (one-time)
    next_due    = models.DateField()

    # Optional linkage / metadata (kept flexible)
    account     = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    tag         = models.CharField(max_length=50, blank=True)   # e.g. 'Rent', 'Food'
    notes       = models.TextField(blank=True)

    class Meta:
        ordering = ['-next_due', '-id']
        indexes  = [
            models.Index(fields=['user', 'is_recurring', 'next_due']),
        ]

    def clean(self):
        # Validate recurring vs one-time logic
        if self.is_recurring:
            if not self.freq:
                raise ValidationError({'freq': "Frequency is required for recurring expenses."})
            if self.freq == 'PERSONALIZED' and not self.freq_custom:
                raise ValidationError({'freq_custom': "Number of days is required for personalized frequency."})
            if self.freq != 'PERSONALIZED' and self.freq_custom:
                raise ValidationError({'freq_custom': "Must be empty unless frequency is 'PERSONALIZED'."})
        else:
            # one-time: frequency fields must not be filled
            if self.freq or self.freq_custom:
                raise ValidationError("One-time expense must not have frequency fields set.")

    def __str__(self):
        if self.is_recurring:
            label = f"Personalized ({self.freq_custom}d)" if self.freq == 'PERSONALIZED' else self.get_freq_display()
            return f"{self.name} – {self.amount} – {label}"
        return f"{self.name} – {self.amount} – one-time on {self.next_due:%Y-%m-%d}"

# ── Proxy model for backward compatibility with current code ("Subscriptions") ──
class RecurringManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_recurring=True)

class Subscription(Expense):
    """Proxy to keep current code working. Returns only recurring expenses."""
    objects = RecurringManager()
    class Meta:
        proxy = True
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

# Optional: proxy for one-time expenses (could be useful later)
class OneTimeExpenseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_recurring=False)

class OneTimeExpense(Expense):
    """Proxy model for one-time expenses (optional helper)."""
    objects = OneTimeExpenseManager()
    class Meta:
        proxy = True
        verbose_name = "One-time expense"
        verbose_name_plural = "One-time expenses"

# ════════════════════════════════════════════════════════════════
# 6) Income (unchanged)
# ════════════════════════════════════════════════════════════════
class Income(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    name        = models.CharField(max_length=255)
    amount      = models.DecimalField(max_digits=15, decimal_places=2)
    freq        = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    freq_custom = models.IntegerField(null=True, blank=True)
    next_payday = models.DateField()

    def clean(self):
        if self.freq == 'PERSONALIZED' and not self.freq_custom:
            raise ValidationError({'freq_custom': "Nombre de jours requis."})
        if self.freq != 'PERSONALIZED' and self.freq_custom:
            raise ValidationError({'freq_custom': "Doit être vide si fréquence standard."})

    def __str__(self):
        label = f"Personnalisé ({self.freq_custom} j)" if self.freq == 'PERSONALIZED' else self.get_freq_display()
        return f"{self.name} – {self.amount} – {label}"

# ════════════════════════════════════════════════════════════════
# 7) Balance History (unchanged)
# ════════════════════════════════════════════════════════════════
class BalanceHistory(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='history')
    date    = models.DateField(default=timezone.now)
    balance = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.account.name} – {self.date} – {self.balance}"

# ════════════════════════════════════════════════════════════════
# 8) Notifications & Dividends (unchanged)
# ════════════════════════════════════════════════════════════════
class Notification(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    message  = models.TextField()
    created  = models.DateTimeField(auto_now_add=True)
    read     = models.BooleanField(default=False)

    def __str__(self):
        return f"Notif {self.user.username} – {self.created:%Y-%m-%d %H:%M}"

class Dividend(models.Model):
    user   = models.ForeignKey(User, on_delete=models.CASCADE)
    asset  = models.ForeignKey(Asset, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date   = models.DateField()

    def __str__(self):
        return f"Dividende {self.asset.ticker} – {self.amount} – {self.date}"

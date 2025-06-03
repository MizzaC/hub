# FundBoard/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

# ════════════════════════════════════════════════════════════════
# ENUM / CHOICES
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
# 1.  Modèle unique Account  (remplace CompteBancaire + InvestmentAccount)
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
# 2.  Assets & Price history
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
    asset            = models.ForeignKey(Asset, on_delete=models.CASCADE)
    date             = models.DateField()
    open_price       = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    high_price       = models.DecimalField(max_digits=15, decimal_places=2)
    low_price        = models.DecimalField(max_digits=15, decimal_places=2)
    close_price      = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    volume           = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('asset', 'date')

    def __str__(self):
        return f"{self.asset.ticker} – {self.date}"

# ════════════════════════════════════════════════════════════════
# 3.  Transactions (FK vers Account uniquement)
# ════════════════════════════════════════════════════════════════
class Transaction(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    account     = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    asset       = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True)
    amount      = models.DecimalField(max_digits=15, decimal_places=2)
    quantity    = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    unit_price  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date_trx    = models.DateTimeField(default=timezone.now)
    trx_type    = models.CharField(max_length=20, choices=TRANSACTION_TYPES)

    def __str__(self):
        return f"{self.get_trx_type_display()} – {self.amount} – {self.date_trx:%d/%m/%Y}"

# ════════════════════════════════════════════════════════════════
# 4.  Watchlists
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
# 5.  Abonnements & Revenus
# ════════════════════════════════════════════════════════════════
class Subscription(models.Model):
    user   = models.ForeignKey(User, on_delete=models.CASCADE)
    name   = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    freq   = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    freq_custom = models.IntegerField(
        null=True, blank=True,
        help_text="Si 'Personnalisé', nombre de jours entre chaque paiement"
    )
    next_due = models.DateField()

    def clean(self):
        if self.freq == 'PERSONALIZED' and not self.freq_custom:
            raise ValidationError({'freq_custom': "Nombre de jours requis."})
        if self.freq != 'PERSONALIZED' and self.freq_custom:
            raise ValidationError({'freq_custom': "Doit être vide si fréquence standard."})

    def __str__(self):
        label = f"Personnalisé ({self.freq_custom} j)" if self.freq == 'PERSONALIZED' else self.get_freq_display()
        return f"{self.name} – {self.amount} – {label}"

class Income(models.Model):
    user   = models.ForeignKey(User, on_delete=models.CASCADE)
    name   = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    freq   = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
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
# 6.  Historique de solde
# ════════════════════════════════════════════════════════════════
class BalanceHistory(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='history')
    date    = models.DateField(default=timezone.now)
    balance = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.account.name} – {self.date} – {self.balance}"

# ════════════════════════════════════════════════════════════════
# 7.  Notifications & Dividendes (inchangés, mais FK vers Account si pertinent)
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

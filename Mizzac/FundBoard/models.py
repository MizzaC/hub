# FundBoard/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

ACCOUNT_TYPES = [
    ('CURRENT',  'Compte courant'),
    ('SAVINGS',  'Livret / Épargne'),
    ('CTO',      'Compte Titres Ordinaire'),
    ('PEA',      'Plan d’Épargne en Actions'),
    ('CRYPTO',   'Portefeuille Crypto'),
    ('OTHER',    'Autre'),
]

# Choices pour les types de comptes d'investissement
INVESTMENT_ACCOUNT_TYPES = [
    ('CTO', 'Compte Titres Ordinaire'),
    ('PEA', 'Plan d\'Épargne en Actions'),
    ('CRYPTO', 'Compte Cryptomonnaie'),
]

# Choices pour les types de transactions
TRANSACTION_TYPES = [
    ('DEPOSIT', 'Dépôt'),
    ('WITHDRAWAL', 'Retrait'),
    ('BUY', 'Achat'),
    ('SELL', 'Vente'),
    ('TRANSFER', 'Transfert'),
]

# Choices pour les fréquences des abonnements et revenus
FREQUENCY_CHOICES = [
    ('DAILY', 'Quotidien'),
    ('WEEKLY', 'Hebdomadaire'),
    ('MONTHLY', 'Mensuel'),
    ('YEARLY', 'Annuel'),
    ('PERSONALIZED', 'Personnalisé'),
]

class CompteBancaire(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    nom          = models.CharField(max_length=255)
    type_compte  = models.CharField(max_length=10, choices=ACCOUNT_TYPES, default='CURRENT')
    solde        = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True)
    devise       = models.CharField(max_length=10, default='EUR', editable=False)

    def __str__(self):
        return f"{self.nom} – {self.get_type_compte_display()} ({self.user.username})"

class InvestmentAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)
    type_compte = models.CharField(max_length=10, choices=INVESTMENT_ACCOUNT_TYPES)
    solde = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    devise = models.CharField(max_length=10)
    # Future API integrations
    api_connected = models.BooleanField(default=False)
    api_service = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.nom} - {self.get_type_compte_display()} ({self.user.username})"


class Asset(models.Model):
    """
    Représente les actifs disponibles (actions, cryptomonnaies).
    """
    ASSET_TYPES = [
        ('STOCK', 'Action'),
        ('CRYPTO', 'Cryptomonnaie'),
        ('ETF', 'Fonds négocié en bourse'),
        ('FOREX', 'Paire de devises'),
        ('OBLIGATION', 'Obligation')
    ]

    nom = models.CharField(max_length=255)
    ticker = models.CharField(max_length=20, unique=True)
    type_asset = models.CharField(max_length=10, choices=ASSET_TYPES)
    secteur = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.nom} ({self.ticker})"

class PriceHistory(models.Model):
    """
    Stocke les données historiques des cours des actifs.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    date = models.DateField()
    valeur_ouverture = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valeur_haute = models.DecimalField(max_digits=15, decimal_places=2)
    valeur_basse = models.DecimalField(max_digits=15, decimal_places=2)
    valeur_fermeture = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    volume_echange = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('asset', 'date')

    def __str__(self):
        return f"{self.asset.ticker} - {self.date}"

class Transaction(models.Model):
    """
    Enregistre toutes les transactions financières de l'utilisateur.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    compte_bancaire = models.ForeignKey(CompteBancaire, on_delete=models.CASCADE, null=True, blank=True)
    investment_account = models.ForeignKey(InvestmentAccount, on_delete=models.CASCADE, null=True, blank=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    quantite = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    prix_unitaire = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date_transaction = models.DateTimeField(default=timezone.now)
    type_transaction = models.CharField(max_length=20, choices=TRANSACTION_TYPES)

    def __str__(self):
        return f"{self.get_type_transaction_display()} - {self.montant} - {self.date_transaction.strftime('%d/%m/%Y %H:%M')}"

class ListeSuivi(models.Model):
    """
    Permet aux utilisateurs de créer des listes de suivi pour surveiller des actifs spécifiques.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.nom} ({self.user.username})"

class SuiviAsset(models.Model):
    """
    Table de liaison entre ListeSuivi et Asset.
    """
    liste_suivi = models.ForeignKey(ListeSuivi, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.liste_suivi.nom} - {self.asset.ticker}"

class Abonnement(models.Model):
    """
    Gère les abonnements et les dépenses récurrentes de l'utilisateur.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    frequence = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    frequence_personnalisee = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Nombre de jours entre chaque paiement (nécessaire si 'Personnalisé' est sélectionné)"
    )
    date_prochaine_echeance = models.DateField()

    def clean(self):
        # Validation pour s'assurer que frequence_personnalisee est fourni si frequence est 'PERSONALIZED'
        if self.frequence == 'PERSONALIZED' and not self.frequence_personnalisee:
            raise ValidationError({
                'frequence_personnalisee': "Veuillez spécifier le nombre de jours pour une fréquence personnalisée."
            })
        if self.frequence != 'PERSONALIZED' and self.frequence_personnalisee:
            raise ValidationError({
                'frequence_personnalisee': "Ce champ doit être vide si la fréquence n'est pas personnalisée."
            })

    def __str__(self):
        if self.frequence == 'PERSONALIZED' and self.frequence_personnalisee:
            frequence_display = f"Personnalisé ({self.frequence_personnalisee} jours)"
        else:
            frequence_display = self.get_frequence_display()
        return f"{self.nom} - {self.montant} {frequence_display}"

class Revenu(models.Model):
    """
    Enregistre les différentes sources de revenus de l'utilisateur.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    frequence = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    frequence_personnalisee = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Nombre de jours entre chaque paiement (nécessaire si 'Personnalisé' est sélectionné)"
    )
    date_prochain_paiement = models.DateField()

    def clean(self):
        # Validation pour s'assurer que frequence_personnalisee est fourni si frequence est 'PERSONALIZED'
        if self.frequence == 'PERSONALIZED' and not self.frequence_personnalisee:
            raise ValidationError({
                'frequence_personnalisee': "Veuillez spécifier le nombre de jours pour une fréquence personnalisée."
            })
        if self.frequence != 'PERSONALIZED' and self.frequence_personnalisee:
            raise ValidationError({
                'frequence_personnalisee': "Ce champ doit être vide si la fréquence n'est pas personnalisée."
            })

    def __str__(self):
        if self.frequence == 'PERSONALIZED' and self.frequence_personnalisee:
            frequence_display = f"Personnalisé ({self.frequence_personnalisee} jours)"
        else:
            frequence_display = self.get_frequence_display()
        return f"{self.nom} - {self.montant} {frequence_display}"

class Devise(models.Model):
    """
    Gère les devises et leurs taux de change.
    """
    code = models.CharField(max_length=10, unique=True)
    taux_change = models.DecimalField(max_digits=15, decimal_places=6)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.taux_change}"

class HistoriqueSolde(models.Model):
    """
    Garde une trace des variations de solde des comptes bancaires au fil du temps.
    """
    compte_bancaire = models.ForeignKey(CompteBancaire, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    solde = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.compte_bancaire.nom} - {self.date} - {self.solde}"

class Notification(models.Model):
    """
    Gère les notifications pour les dates d'échéance des abonnements ou les variations importantes du marché.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification pour {self.user.username} - {self.date_creation}"

# Optionnel: Modèle pour les dividendes
class Dividende(models.Model):
    """
    Enregistre les dividendes reçus pour chaque action.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    date_reception = models.DateField()

    def __str__(self):
        return f"Dividende {self.asset.ticker} - {self.montant} - {self.date_reception}"

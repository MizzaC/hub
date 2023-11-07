from django.db import models
from jsonfield import JSONField

from django.db import models

class Stock(models.Model):
    name = models.CharField(max_length=200)
    ticker = models.CharField(max_length=10)
    mnemonic_code = models.CharField(max_length=10)

    def __str__(self):
        return self.name

class BankAccount(models.Model):
    account_number = models.CharField(max_length=20)
    account_holder = models.CharField(max_length=200)

    def __str__(self):
        return self.account_number

class StockOwnership(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    
    def __str__(self):
        return f"{self.bank_account.account_number} owns {self.quantity} of {self.stock.name}"

class StockPriceHistory(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()

    def __str__(self):
        return f"{self.stock.name} - {self.price} on {self.date}"

class StockOwnershipHistory(models.Model):
    stock_ownership = models.ForeignKey(StockOwnership, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    date = models.DateField()

    def __str__(self):
        return f"{self.stock_ownership.bank_account.account_number} owned {self.quantity} of {self.stock_ownership.stock.name} on {self.date}"

class BankAccountHistory(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()

    def __str__(self):
        return f"Total value of {self.bank_account.account_number} was {self.total_value} on {self.date}"


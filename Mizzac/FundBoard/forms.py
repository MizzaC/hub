# FundBoard/forms.py
from django import forms

from .models import (
    Subscription, Income,
    Account
)

# ──────────────────────────────────────────────────────────────
class SubscriptionForm(forms.ModelForm):
    class Meta:
        model  = Subscription
        fields = ['name', 'amount', 'freq', 'freq_custom', 'next_due']
        labels = {
            'name':  'Nom de l’abonnement',
            'amount':'Montant',
            'freq':  'Fréquence',
            'freq_custom':'Jours (si personnalisé)',
            'next_due':'Prochaine échéance'
        }
        widgets = {
            'next_due': forms.DateInput(attrs={'type':'date', 'class':'form-control'}),
            'freq_custom': forms.NumberInput(attrs={'min':1, 'class':'form-control'}),
        }

# ──────────────────────────────────────────────────────────────
class IncomeForm(forms.ModelForm):
    class Meta:
        model  = Income
        fields = ['name', 'amount', 'freq', 'freq_custom', 'next_payday']
        labels = {
            'name':'Source',
            'amount':'Montant',
            'freq':'Fréquence',
            'freq_custom':'Jours (si personnalisé)',
            'next_payday':'Prochain paiement',
        }
        widgets = {
            'next_payday': forms.DateInput(attrs={'type':'date', 'class':'form-control'}),
            'freq_custom': forms.NumberInput(attrs={'min':1, 'class':'form-control'}),
        }

# ──────────────────────────────────────────────────────────────
class ManualAccountForm(forms.ModelForm):
    class Meta:
        model  = Account
        fields = ['name', 'category', 'balance']
        labels = {
            'name':'Nom du compte',
            'category':'Type',
            'balance':'Solde initial (optionnel)',
        }
        widgets = {
            'name':     forms.TextInput(attrs={'class':'form-control'}),
            'category': forms.Select(attrs={'class':'form-select'}),
            'balance':  forms.NumberInput(attrs={'class':'form-control', 'step':'0.01'}),
        }

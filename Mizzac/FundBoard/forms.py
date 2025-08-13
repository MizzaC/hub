# FundBoard/forms.py
from django import forms

from .models import (
    Expense, Income, Account
)

# ──────────────────────────────────────────────────────────────
# Unified Expense form (recurring OR one-time)
# - is_recurring toggles the visibility/need of freq fields
# - account is optional for now (kept in the form for future link)
# ──────────────────────────────────────────────────────────────
class ExpenseForm(forms.ModelForm):
    class Meta:
        model  = Expense
        fields = ['is_recurring', 'name', 'amount', 'next_due', 'freq', 'freq_custom', 'account', 'tag', 'notes']
        labels = {
            'is_recurring': 'Recurring expense',
            'name':        'Name',
            'amount':      'Amount',
            'next_due':    'Date / Next due',
            'freq':        'Frequency',
            'freq_custom': 'Days (if personalized)',
            'account':     'Linked account (optional)',
            'tag':         'Tag (optional)',
            'notes':       'Notes (optional)',
        }
        widgets = {
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'name':        forms.TextInput(attrs={'class':'form-control', 'placeholder':'e.g. Netflix / Rent / Groceries'}),
            'amount':      forms.NumberInput(attrs={'class':'form-control', 'step':'0.01', 'min':'0'}),
            'next_due':    forms.DateInput(attrs={'type':'date', 'class':'form-control'}),
            'freq':        forms.Select(attrs={'class':'form-select'}),
            'freq_custom': forms.NumberInput(attrs={'min':1, 'class':'form-control'}),
            'account':     forms.Select(attrs={'class':'form-select'}),
            'tag':         forms.TextInput(attrs={'class':'form-control', 'placeholder':'e.g. Food, Housing'}),
            'notes':       forms.Textarea(attrs={'class':'form-control', 'rows':3}),
        }

# ──────────────────────────────────────────────────────────────
# Income form (unchanged)
# ──────────────────────────────────────────────────────────────
class IncomeForm(forms.ModelForm):
    class Meta:
        model  = Income
        fields = ['name', 'amount', 'freq', 'freq_custom', 'next_payday']
        labels = {
            'name':        'Source',
            'amount':      'Amount',
            'freq':        'Frequency',
            'freq_custom': 'Days (if personalized)',
            'next_payday': 'Next payday',
        }
        widgets = {
            'name':        forms.TextInput(attrs={'class':'form-control'}),
            'amount':      forms.NumberInput(attrs={'class':'form-control', 'step':'0.01', 'min':'0'}),
            'freq':        forms.Select(attrs={'class':'form-select'}),
            'freq_custom': forms.NumberInput(attrs={'min':1, 'class':'form-control'}),
            'next_payday': forms.DateInput(attrs={'type':'date', 'class':'form-control'}),
        }

# ──────────────────────────────────────────────────────────────
# Manual account form (unchanged)
# ──────────────────────────────────────────────────────────────
class ManualAccountForm(forms.ModelForm):
    class Meta:
        model  = Account
        fields = ['name', 'category', 'balance']
        labels = {
            'name':'Account name',
            'category':'Type',
            'balance':'Initial balance (optional)',
        }
        widgets = {
            'name':     forms.TextInput(attrs={'class':'form-control'}),
            'category': forms.Select(attrs={'class':'form-select'}),
            'balance':  forms.NumberInput(attrs={'class':'form-control', 'step':'0.01'}),
        }

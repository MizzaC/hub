# FundBoard/forms.py
from django import forms

from .models import (
    Expense, Income, Account
)

# ──────────────────────────────────────────────────────────────
# Unified Expense form (recurring OR one-time)
# UX goals:
# - Show frequency fields only if is_recurring=True (handled in template JS)
# - Server-side clean() guarantees coherence whatever the UI does
# - Labels in French for consistency; comments in English
# ──────────────────────────────────────────────────────────────
class ExpenseForm(forms.ModelForm):
    class Meta:
        model  = Expense
        fields = [
            'is_recurring', 'name', 'amount', 'next_due',
            'freq', 'freq_custom',
            'account', 'tag', 'notes'
        ]
        labels = {
            'is_recurring': 'Dépense récurrente',
            'name':        'Nom',
            'amount':      'Montant',
            'next_due':    'Date / Prochaine échéance',
            'freq':        'Fréquence',
            'freq_custom': 'Jours (si personnalisé)',
            'account':     'Compte lié (optionnel)',
            'tag':         'Catégorie / Tag (optionnel)',
            'notes':       'Notes (optionnel)',
        }
        widgets = {
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'name':        forms.TextInput(attrs={
                                'class':'form-control',
                                'placeholder':'ex. Netflix, Loyer, Courses'
                             }),
            'amount':      forms.NumberInput(attrs={
                                'class':'form-control',
                                'step':'0.01', 'min':'0', 'inputmode':'decimal'
                             }),
            'next_due':    forms.DateInput(attrs={'type':'date', 'class':'form-control'}),
            'freq':        forms.Select(attrs={'class':'form-select'}),
            'freq_custom': forms.NumberInput(attrs={'min':1, 'class':'form-control'}),
            'account':     forms.Select(attrs={'class':'form-select'}),
            'tag':         forms.TextInput(attrs={
                                'class':'form-control',
                                'placeholder':'ex. Logement, Alimentaire'
                             }),
            'notes':       forms.Textarea(attrs={'class':'form-control', 'rows':3}),
        }

    def clean(self):
        """
        Enforce coherent state:
        - If not recurring → freq & freq_custom must be empty
        - If recurring     → freq is required; if freq == PERSONALIZED → freq_custom required
        - Clear unused fields so the DB stays clean
        """
        cleaned = super().clean()
        is_rec  = cleaned.get('is_recurring')
        freq    = cleaned.get('freq')
        custom  = cleaned.get('freq_custom')

        if is_rec:
            # Recurring: frequency required
            if not freq:
                self.add_error('freq', "Veuillez sélectionner une fréquence.")
            # Personalized: number of days required
            if freq == 'PERSONALIZED' and not custom:
                self.add_error('freq_custom', "Veuillez saisir le nombre de jours pour une fréquence personnalisée.")
            # If not personalized, ensure freq_custom is cleared
            if freq != 'PERSONALIZED':
                cleaned['freq_custom'] = None
        else:
            # One-time: strip any accidental frequency values
            cleaned['freq'] = None
            cleaned['freq_custom'] = None

        return cleaned


# ──────────────────────────────────────────────────────────────
# Income form (unchanged)
# ──────────────────────────────────────────────────────────────
class IncomeForm(forms.ModelForm):
    class Meta:
        model  = Income
        fields = ['name', 'amount', 'freq', 'freq_custom', 'next_payday']
        labels = {
            'name':        'Source',
            'amount':      'Montant',
            'freq':        'Fréquence',
            'freq_custom': 'Jours (si personnalisé)',
            'next_payday': 'Prochain paiement',
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
            'name':'Nom du compte',
            'category':'Type',
            'balance':'Solde initial (optionnel)',
        }
        widgets = {
            'name':     forms.TextInput(attrs={'class':'form-control'}),
            'category': forms.Select(attrs={'class':'form-select'}),
            'balance':  forms.NumberInput(attrs={'class':'form-control', 'step':'0.01'}),
        }

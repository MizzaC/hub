# FundBoard/forms.py
from decimal import Decimal
from django import forms
from django.utils import timezone

from .models import Expense, Income, Account, Transaction, Asset


# ──────────────────────────────────────────────────────────────
# Expense form (one-time or recurring)
# ──────────────────────────────────────────────────────────────
class ExpenseForm(forms.ModelForm):
    class Meta:
        model  = Expense
        fields = [
            'is_recurring', 'name', 'amount', 'next_due',
            'freq', 'freq_custom',
            'account', 'tag', 'notes',
        ]
        labels = {
            'is_recurring': 'Dépense récurrente',
            'name':        'Nom',
            'amount':      'Montant',
            'next_due':    'Date / prochaine échéance',
            'freq':        'Fréquence',
            'freq_custom': 'Jours (si personnalisé)',
            'account':     'Compte lié (optionnel)',
            'tag':         'Catégorie / Tag (optionnel)',
            'notes':       'Notes (optionnel)',
        }
        widgets = {
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'name':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex. Loyer, Netflix, Courses'}),
            'amount':       forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
            'next_due':     forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'freq':         forms.Select(attrs={'class': 'form-select'}),
            'freq_custom':  forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'account':      forms.Select(attrs={'class': 'form-select'}),
            'tag':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex. Logement, Alimentaire'}),
            'notes':        forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        """Enforce recurrence fields only when is_recurring=True."""
        cleaned = super().clean()
        is_rec  = cleaned.get('is_recurring')
        freq    = cleaned.get('freq')
        custom  = cleaned.get('freq_custom')

        if is_rec:
            if not freq:
                self.add_error('freq', "Veuillez sélectionner une fréquence.")
            if freq == 'PERSONALIZED' and not custom:
                self.add_error('freq_custom', "Veuillez saisir le nombre de jours.")
            if freq != 'PERSONALIZED':
                cleaned['freq_custom'] = None
        else:
            cleaned['freq'] = None
            cleaned['freq_custom'] = None
        return cleaned
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Only show accounts owned by the current user
            self.fields['account'].queryset = Account.objects.filter(user=user)


# ──────────────────────────────────────────────────────────────
# Income form (one-time or recurring)
# ──────────────────────────────────────────────────────────────
class IncomeForm(forms.ModelForm):
    class Meta:
        model  = Income
        fields = ['is_recurring', 'name', 'amount', 'next_payday', 'freq', 'freq_custom', 'notes']
        labels = {
            'is_recurring': 'Revenu récurrent',
            'name':        'Source',
            'amount':      'Montant',
            'next_payday': 'Date / prochain paiement',
            'freq':        'Fréquence',
            'freq_custom': 'Jours (si personnalisé)',
            'notes':       'Notes (optionnel)',
        }
        widgets = {
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'name':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex. Salaire, Prime'}),
            'amount':       forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'next_payday':  forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'freq':         forms.Select(attrs={'class': 'form-select'}),
            'freq_custom':  forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'notes':        forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        """Enforce recurrence fields only when is_recurring=True."""
        cleaned = super().clean()
        is_rec  = cleaned.get('is_recurring')
        freq    = cleaned.get('freq')
        custom  = cleaned.get('freq_custom')

        if is_rec:
            if not freq:
                self.add_error('freq', "Veuillez sélectionner une fréquence.")
            if freq == 'PERSONALIZED' and not custom:
                self.add_error('freq_custom', "Veuillez saisir le nombre de jours.")
            if freq != 'PERSONALIZED':
                cleaned['freq_custom'] = None
        else:
            cleaned['freq'] = None
            cleaned['freq_custom'] = None
        return cleaned


# ──────────────────────────────────────────────────────────────
# Manual account form
# ──────────────────────────────────────────────────────────────
class ManualAccountForm(forms.ModelForm):
    class Meta:
        model  = Account
        fields = ['name', 'category', 'balance']
        labels = {
            'name':     'Nom du compte',
            'category': 'Type',
            'balance':  'Solde initial (optionnel)',
        }
        widgets = {
            'name':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex. Compte courant SG'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'balance':  forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


# ──────────────────────────────────────────────────────────────
# Investment trade form (BUY / SELL) → creates a Transaction
# ──────────────────────────────────────────────────────────────
class InvestmentForm(forms.ModelForm):
    """
    Create a BUY/SELL trade; amount is computed from quantity, unit_price and optional fees.
    The view must pass `user` to limit accounts to current user.
    """
    fees = forms.DecimalField(
        label="Frais (optionnel)",
        required=False,
        min_value=Decimal('0'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    class Meta:
        model  = Transaction
        fields = ['account', 'asset', 'trx_type', 'quantity', 'unit_price', 'date_trx', 'memo']
        labels = {
            'account':    'Compte',
            'asset':      'Actif',
            'trx_type':   'Type',
            'quantity':   'Quantité',
            'unit_price': 'Prix unitaire',
            'date_trx':   'Date',
            'memo':       'Note (optionnel)',
        }
        widgets = {
            'account':    forms.Select(attrs={'class': 'form-select'}),
            'asset':      forms.Select(attrs={'class': 'form-select'}),
            'trx_type':   forms.Select(attrs={'class': 'form-select'}),
            'quantity':   forms.NumberInput(attrs={'class': 'form-control', 'step': '0.00000001', 'min': '0'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'date_trx':   forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'memo':       forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, user, *args, **kwargs):
        """Limit choices to current user context & restrict type to BUY/SELL."""
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user).order_by('name')
        self.fields['trx_type'].choices = [('BUY', 'Achat'), ('SELL', 'Vente')]

    def clean(self):
        cleaned    = super().clean()
        trx_type   = cleaned.get('trx_type')
        quantity   = cleaned.get('quantity')   or Decimal('0')
        unit_price = cleaned.get('unit_price') or Decimal('0')

        if trx_type not in ('BUY', 'SELL'):
            self.add_error('trx_type', "Type invalide.")
        if quantity <= 0:
            self.add_error('quantity', "Quantité invalide.")
        if unit_price <= 0:
            self.add_error('unit_price', "Prix unitaire invalide.")
        return cleaned

    def save(self, commit=True):
        """
        Compute amount sign convention:
        - BUY  → negative (cash out)
        - SELL → positive (cash in)
        Save Transaction instance.
        """
        instance: Transaction = super().save(commit=False)
        fees = self.cleaned_data.get('fees') or Decimal('0')
        q    = self.cleaned_data['quantity']
        p    = self.cleaned_data['unit_price']

        if instance.trx_type == 'BUY':
            cash = (q * p) + fees
            instance.amount = -cash
        else:  # SELL
            cash = (q * p) - fees
            instance.amount = cash

        # Append fee info to memo for traceability
        if fees and not (instance.memo or '').strip():
            instance.memo = f"fees={fees}"
        elif fees:
            instance.memo = f"{instance.memo} | fees={fees}"

        if commit:
            instance.save()
        return instance


# ──────────────────────────────────────────────────────────────
# Mark Income as received (creates a DEPOSIT on an account)
# ──────────────────────────────────────────────────────────────
class MarkIncomeForm(forms.Form):
    """
    Non-model form used to post an actual inflow for a planned Income
    to a selected Account with an amount/date override if needed.
    View should create a Transaction(DEPOSIT) based on this data.
    """
    account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="Compte"
    )
    amount = forms.DecimalField(
        label="Montant encaissé",
        min_value=Decimal('0'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    date_posted = forms.DateTimeField(
        label="Date de valeur",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    memo = forms.CharField(
        label="Note (optionnel)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user, income: Income | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user).order_by('name')
        # prefill from income if provided
        if income is not None:
            self.fields['amount'].initial = income.amount
        self.fields['date_posted'].initial = timezone.now()

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Account, Asset, CashflowRule, Transaction


class CashflowRuleForm(forms.ModelForm):
    class Meta:
        model = CashflowRule
        fields = [
            "is_recurring",
            "name",
            "amount",
            "start_date",
            "end_date",
            "next_due",
            "freq",
            "freq_custom",
            "default_account",
            "tag",
            "notes",
        ]
        widgets = {
            "is_recurring": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "next_due": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "freq": forms.Select(attrs={"class": "form-select"}),
            "freq_custom": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "default_account": forms.Select(attrs={"class": "form-select"}),
            "tag": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["default_account"].queryset = Account.objects.filter(user=user).order_by("name")

    def clean(self):
        cleaned = super().clean()
        is_rec = cleaned.get("is_recurring")
        freq = cleaned.get("freq")
        custom = cleaned.get("freq_custom")
        if is_rec:
            if not freq:
                self.add_error("freq", "Veuillez selectionner une frequence.")
            if freq == "PERSONALIZED" and not custom:
                self.add_error("freq_custom", "Veuillez saisir le nombre de jours.")
            if freq != "PERSONALIZED":
                cleaned["freq_custom"] = None
        else:
            cleaned["freq"] = None
            cleaned["freq_custom"] = None
        return cleaned


class ExpenseForm(CashflowRuleForm):
    pass


class IncomeForm(CashflowRuleForm):
    pass


class ManualAccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["name", "category", "base_currency"]
        labels = {
            "name": "Nom du compte",
            "category": "Type",
            "base_currency": "Devise",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "base_currency": forms.TextInput(attrs={"class": "form-control", "maxlength": 10}),
        }


class InvestmentForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), label="Compte")
    asset = forms.ModelChoiceField(queryset=Asset.objects.all().order_by("ticker"), label="Actif")
    cash_asset = forms.ModelChoiceField(queryset=Asset.objects.none(), label="Actif de tresorerie")
    trx_type = forms.ChoiceField(choices=[("BUY", "Achat"), ("SELL", "Vente")], label="Type")
    quantity = forms.DecimalField(min_value=Decimal("0.000000000001"), decimal_places=12)
    unit_price_reference = forms.DecimalField(min_value=Decimal("0.00000001"), decimal_places=12)
    fees = forms.DecimalField(required=False, min_value=Decimal("0"), decimal_places=12)
    executed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )
    description = forms.CharField(required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accounts = Account.objects.filter(user=user).order_by("name")
        self.fields["account"].queryset = accounts
        self.fields["cash_asset"].queryset = Asset.objects.filter(asset_type="FIAT").order_by("ticker")
        self.fields["executed_at"].initial = timezone.now()


class MarkIncomeForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), label="Compte")
    amount = forms.DecimalField(
        label="Montant encaisse",
        min_value=Decimal("0"),
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    date_posted = forms.DateTimeField(
        label="Date de valeur",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )
    memo = forms.CharField(
        label="Note (optionnel)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, user, income_rule: CashflowRule | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(user=user).order_by("name")
        if income_rule is not None:
            self.fields["amount"].initial = income_rule.amount
            self.fields["account"].initial = income_rule.default_account
        self.fields["date_posted"].initial = timezone.now()


class TransactionFilterForm(forms.Form):
    trx_type = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + list(Transaction._meta.get_field("trx_type").choices),
    )

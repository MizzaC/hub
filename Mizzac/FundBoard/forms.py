from django import forms
from django.db.models import Q

from .integrations.connectors import get_connector
from .integrations.connectors.base import ConnectorError
from .models import (
    Account,
    CompoundInterestScenario,
    Income,
    Instrument,
    Loan,
    LoanBalanceSnapshot,
    LoanSimulationScenario,
    MarketDataPreference,
    Position,
    PrivateEquityHolding,
    PrivateEquityValuation,
    RealEstate,
    RealEstateValuation,
    Subscription,
    Transaction,
    VirtualCorporateAction,
    VirtualOrder,
    VirtualPortfolio,
)
from .services.compound_interest import (
    CompoundInterestAssumptions,
    calculate_compound_interest,
)
from .services.loan_calculator import LoanAssumptions, calculate_loan
from .services.paper_trading import default_fractional_permission

CONNECTOR_CHOICES = (
    ("enable_banking", "Compte bancaire — Enable Banking"),
    (
        "trade_republic_psd2",
        "Trade Republic — compte courant automatique (PSD2)",
    ),
    ("binance", "Binance Spot — API en lecture seule"),
    ("ledger_live", "Ledger Live — import CSV local"),
    ("trade_republic", "Trade Republic — import expérimental"),
)


class TablerFormMixin:
    """Apply the shared Tabler form classes without duplicating widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, forms.Select):
                css_class = "form-select"
            else:
                css_class = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css_class}".strip()


class UserScopedFormMixin:
    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def account_queryset(self):
        return Account.objects.filter(user=self.user, status=Account.Status.ACTIVE)

    def instrument_queryset(self):
        return Instrument.objects.filter(
            Q(owner=self.user) | Q(owner__isnull=True),
            status=Instrument.Status.ACTIVE,
        )


class ConnectorForm(TablerFormMixin, forms.Form):
    provider = forms.ChoiceField(choices=CONNECTOR_CHOICES, label="Source")
    display_name = forms.CharField(max_length=255, label="Nom affiché")
    bank_name = forms.CharField(
        max_length=100,
        required=False,
        label="Nom Enable Banking de la banque",
        help_text="Nom exact affiché dans le Control Panel Enable Banking.",
    )
    country = forms.CharField(max_length=2, initial="FR", required=False, label="Pays")
    consent_days = forms.IntegerField(
        min_value=1,
        max_value=180,
        initial=180,
        required=False,
        label="Durée de consentement demandée (jours)",
    )
    symbols = forms.CharField(
        initial="BTCUSDT,ETHUSDT",
        required=False,
        label="Paires Binance à historiser",
        help_text="20 paires maximum, séparées par des virgules.",
    )
    experimental_accepted = forms.BooleanField(
        required=False,
        label="J'accepte l'import Trade Republic expérimental et non officiel.",
    )

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get("provider")
        if not provider:
            return cleaned
        configuration = {}
        if provider == "enable_banking":
            configuration = {
                "bank_name": cleaned.get("bank_name", ""),
                "country": cleaned.get("country", "FR"),
                "consent_days": cleaned.get("consent_days") or 180,
            }
        elif provider == "trade_republic_psd2":
            configuration = {
                "bank_name": "Trade Republic",
                "country": "DE",
                "consent_days": 180,
                "trade_republic_cash_only": True,
                "requires_stable_transaction_id": True,
            }
        elif provider == "binance":
            configuration = {"symbols": cleaned.get("symbols", ""), "initial_days": 90}
        elif provider == "trade_republic":
            configuration = {"experimental_accepted": cleaned.get("experimental_accepted", False)}
        try:
            connector_provider = (
                "enable_banking" if provider == "trade_republic_psd2" else provider
            )
            validated = get_connector(connector_provider).validate_configuration(configuration)
            validated.update(
                {
                    key: value
                    for key, value in configuration.items()
                    if key in {"trade_republic_cash_only", "requires_stable_transaction_id"}
                }
            )
            cleaned["configuration"] = validated
            cleaned["connector_provider"] = connector_provider
        except ConnectorError as exc:
            raise forms.ValidationError(exc.public_message) from exc
        return cleaned


class ConnectorImportForm(TablerFormMixin, forms.Form):
    file = forms.FileField(label="Export à importer")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Le fichier dépasse 5 Mio.")
        return upload


class SubscriptionForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ["name", "amount", "currency", "freq", "freq_custom", "next_due"]
        labels = {
            "name": "Nom de l’abonnement",
            "amount": "Montant",
            "currency": "Devise",
            "freq": "Fréquence",
            "freq_custom": "Jours (si personnalisé)",
            "next_due": "Prochaine échéance",
        }
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.00000001"}),
            "currency": forms.TextInput(attrs={"maxlength": 3, "placeholder": "EUR"}),
            "next_due": forms.DateInput(attrs={"type": "date"}),
            "freq_custom": forms.NumberInput(attrs={"min": 1}),
        }


class IncomeForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Income
        fields = ["name", "amount", "currency", "freq", "freq_custom", "next_payday"]
        labels = {
            "name": "Source",
            "amount": "Montant",
            "currency": "Devise",
            "freq": "Fréquence",
            "freq_custom": "Jours (si personnalisé)",
            "next_payday": "Prochain paiement",
        }
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.00000001"}),
            "currency": forms.TextInput(attrs={"maxlength": 3, "placeholder": "EUR"}),
            "next_payday": forms.DateInput(attrs={"type": "date"}),
            "freq_custom": forms.NumberInput(attrs={"min": 1}),
        }


class ManualAccountForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Account
        fields = [
            "manual_reference",
            "name",
            "category",
            "subtype",
            "balance",
            "currency",
            "ownership_share",
            "iban_masked",
            "status",
        ]
        error_messages = {
            "currency": {"max_length": "Utilisez un code devise ISO sur trois lettres."}
        }
        labels = {
            "manual_reference": "Référence personnelle",
            "name": "Nom du compte",
            "category": "Type",
            "subtype": "Sous-type",
            "balance": "Trésorerie / solde",
            "currency": "Devise",
            "ownership_share": "Quote-part (%)",
            "iban_masked": "IBAN masqué",
            "status": "Statut",
        }
        widgets = {
            "balance": forms.NumberInput(attrs={"step": "0.00000001"}),
            "currency": forms.TextInput(attrs={"maxlength": 3, "placeholder": "EUR"}),
            "ownership_share": forms.NumberInput(attrs={"min": "0.01", "max": 100, "step": "0.01"}),
            "iban_masked": forms.TextInput(attrs={"placeholder": "FR76 •••• 1234"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ownership_share"].required = False
        self.fields["status"].required = False

    def clean_currency(self):
        currency = self.cleaned_data["currency"].strip().upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise forms.ValidationError("Utilisez un code devise ISO sur trois lettres.")
        return currency


class InstrumentForm(TablerFormMixin, forms.ModelForm):
    coingecko_id = forms.CharField(
        required=False,
        label="Identifiant CoinGecko",
        help_text="Pour une crypto : bitcoin, ethereum, solana… (pas seulement BTC ou ETH).",
    )

    class Meta:
        model = Instrument
        fields = [
            "manual_reference",
            "name",
            "instrument_type",
            "ticker",
            "isin",
            "market_mic",
            "currency",
            "country_code",
            "sector",
            "blockchain",
            "contract_address",
            "status",
        ]
        labels = {
            "manual_reference": "Référence personnelle",
            "name": "Nom",
            "instrument_type": "Type",
            "ticker": "Ticker",
            "isin": "ISIN",
            "market_mic": "Place (MIC)",
            "currency": "Devise",
            "country_code": "Pays",
            "sector": "Secteur",
            "blockchain": "Blockchain",
            "contract_address": "Contrat du token",
            "status": "Statut",
        }
        widgets = {
            "currency": forms.TextInput(attrs={"maxlength": 3, "placeholder": "EUR"}),
            "country_code": forms.TextInput(attrs={"maxlength": 2, "placeholder": "FR"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["coingecko_id"].initial = self.instance.provider_identifiers.get(
                "coingecko",
                "",
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        identifiers = dict(instance.provider_identifiers)
        coingecko_id = self.cleaned_data.get("coingecko_id", "").strip().lower()
        if coingecko_id:
            identifiers["coingecko"] = coingecko_id
        else:
            identifiers.pop("coingecko", None)
        instance.provider_identifiers = identifiers
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PositionForm(UserScopedFormMixin, TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Position
        fields = [
            "account",
            "instrument",
            "quantity",
            "average_unit_cost",
            "cost_basis",
            "current_unit_price",
            "current_value",
            "value_currency",
            "valued_at",
            "status",
        ]
        labels = {
            "account": "Compte contenant",
            "instrument": "Instrument",
            "quantity": "Quantité",
            "average_unit_cost": "Prix de revient unitaire",
            "cost_basis": "Coût total",
            "current_unit_price": "Cours actuel",
            "current_value": "Valeur actuelle",
            "value_currency": "Devise de valorisation",
            "valued_at": "Date et heure de valorisation",
            "status": "Statut",
        }
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.000000000000000001"}),
            "average_unit_cost": forms.NumberInput(attrs={"step": "0.000000000001"}),
            "cost_basis": forms.NumberInput(attrs={"step": "0.00000001"}),
            "current_unit_price": forms.NumberInput(attrs={"step": "0.000000000001"}),
            "current_value": forms.NumberInput(attrs={"step": "0.00000001"}),
            "value_currency": forms.TextInput(attrs={"maxlength": 3}),
            "valued_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = self.account_queryset()
        self.fields["instrument"].queryset = self.instrument_queryset()


class TransactionForm(UserScopedFormMixin, TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            "account",
            "instrument",
            "transaction_type",
            "subtype",
            "quantity",
            "unit_price",
            "gross_amount",
            "fees",
            "taxes",
            "net_amount",
            "currency",
            "executed_at",
            "value_date",
            "label",
            "status",
        ]
        labels = {
            "account": "Compte",
            "instrument": "Instrument",
            "transaction_type": "Type",
            "subtype": "Sous-type",
            "quantity": "Quantité",
            "unit_price": "Prix unitaire",
            "gross_amount": "Montant brut",
            "fees": "Frais",
            "taxes": "Taxes",
            "net_amount": "Montant net signé",
            "currency": "Devise",
            "executed_at": "Date et heure d’opération",
            "value_date": "Date de valeur",
            "label": "Libellé",
            "status": "Statut",
        }
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.000000000000000001"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.000000000001"}),
            "gross_amount": forms.NumberInput(attrs={"step": "0.00000001"}),
            "fees": forms.NumberInput(attrs={"min": 0, "step": "0.00000001"}),
            "taxes": forms.NumberInput(attrs={"min": 0, "step": "0.00000001"}),
            "net_amount": forms.NumberInput(attrs={"step": "0.00000001"}),
            "currency": forms.TextInput(attrs={"maxlength": 3}),
            "executed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "value_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = self.account_queryset()
        self.fields["instrument"].queryset = self.instrument_queryset()


class LoanForm(UserScopedFormMixin, TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Loan
        exclude = ["user", "archived", "metadata"]
        labels = {
            "manual_reference": "Référence personnelle",
            "account": "Compte lié",
            "loan_type": "Type de prêt",
            "original_principal": "Capital initial",
            "outstanding_principal": "Capital restant dû",
            "balance_date": "Date du capital restant dû",
            "nominal_rate": "Taux nominal annuel (%)",
            "apr": "TAEG (%)",
            "duration_months": "Durée (mois)",
            "start_date": "Date de début",
            "maturity_date": "Date de fin",
            "payment_amount": "Échéance",
            "insurance_amount": "Assurance par échéance",
            "insurance_rate": "Taux d’assurance (%)",
            "initial_fees": "Frais initiaux",
            "deferred_months": "Différé (mois)",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "balance_date": forms.DateInput(attrs={"type": "date"}),
            "maturity_date": forms.DateInput(attrs={"type": "date"}),
            "currency": forms.TextInput(attrs={"maxlength": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = self.account_queryset()


class RealEstateForm(UserScopedFormMixin, TablerFormMixin, forms.ModelForm):
    class Meta:
        model = RealEstate
        exclude = ["user", "archived", "metadata"]
        labels = {
            "manual_reference": "Référence personnelle",
            "property_type": "Type de bien",
            "surface_sqm": "Surface (m²)",
            "ownership_share": "Quote-part (%)",
            "purchase_price": "Prix d’achat",
            "purchase_costs": "Frais d’acquisition",
            "renovation_costs": "Travaux",
            "estimated_value": "Valeur estimée",
            "valuation_date": "Date de valorisation",
            "valuation_source": "Source de valorisation",
            "monthly_rent": "Loyer mensuel",
            "monthly_charges": "Charges mensuelles",
            "annual_property_tax": "Taxe foncière annuelle",
            "annual_insurance": "Assurance annuelle",
            "annual_other_costs": "Autres coûts annuels",
            "vacancy_rate": "Vacance locative estimée (%)",
            "linked_loan": "Prêt lié",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "currency": forms.TextInput(attrs={"maxlength": 3}),
            "valuation_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["linked_loan"].queryset = Loan.objects.filter(
            user=self.user,
            archived=False,
        )


class RealEstateValuationForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = RealEstateValuation
        fields = ["value", "valuation_date", "source"]
        labels = {
            "value": "Valeur estimée",
            "valuation_date": "Date de valorisation",
            "source": "Source",
        }
        widgets = {"valuation_date": forms.DateInput(attrs={"type": "date"})}


class LoanBalanceSnapshotForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = LoanBalanceSnapshot
        fields = ["outstanding_principal", "observed_on", "source"]
        labels = {
            "outstanding_principal": "Capital restant dû",
            "observed_on": "Date d'observation",
            "source": "Source",
        }
        widgets = {"observed_on": forms.DateInput(attrs={"type": "date"})}


class PrivateEquityForm(UserScopedFormMixin, TablerFormMixin, forms.ModelForm):
    class Meta:
        model = PrivateEquityHolding
        exclude = ["user", "archived", "metadata"]
        labels = {
            "manual_reference": "Référence personnelle",
            "account": "Compte lié",
            "company_or_fund": "Société ou fonds",
            "vintage_year": "Millésime",
            "commitment": "Engagement",
            "called_capital": "Capital appelé",
            "distributions": "Distributions cumulées",
            "net_asset_value": "Valeur liquidative",
            "valuation_date": "Date de valorisation",
            "valuation_source": "Source de valorisation",
            "ownership_share": "Quote-part (%)",
        }
        widgets = {
            "currency": forms.TextInput(attrs={"maxlength": 3}),
            "valuation_date": forms.DateInput(attrs={"type": "date"}),
            "vintage_year": forms.NumberInput(attrs={"min": 1900, "max": 2200}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = self.account_queryset()


class PrivateEquityValuationForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = PrivateEquityValuation
        fields = [
            "net_asset_value",
            "called_capital",
            "distributions",
            "valuation_date",
            "source",
        ]
        labels = {
            "net_asset_value": "Valeur liquidative",
            "called_capital": "Capital appelé cumulé",
            "distributions": "Distributions cumulées",
            "valuation_date": "Date de valorisation",
            "source": "Source",
        }
        widgets = {"valuation_date": forms.DateInput(attrs={"type": "date"})}


class LoanSimulationForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = LoanSimulationScenario
        exclude = ["user", "archived"]
        labels = {
            "name": "Nom du scénario",
            "principal": "Capital emprunté",
            "annual_rate": "Taux nominal annuel (%)",
            "calculation_mode": "Valeur à calculer",
            "duration_months": "Durée totale (mois)",
            "target_payment": "Mensualité cible hors assurance",
            "insurance_mode": "Mode d'assurance",
            "insurance_value": "Montant mensuel ou taux annuel (%)",
            "insurance_basis": "Assiette du taux d'assurance",
            "initial_fees": "Frais initiaux",
            "deferment_months": "Différé (mois)",
            "deferment_type": "Type de différé",
            "one_off_prepayment": "Remboursement anticipé ponctuel",
            "one_off_prepayment_month": "Mois du remboursement ponctuel",
            "recurring_prepayment": "Remboursement anticipé mensuel",
            "recurring_prepayment_start_month": "Premier mois du remboursement mensuel",
            "start_date": "Date de départ",
        }
        help_texts = {
            "duration_months": "Requis pour calculer la mensualité ; différé inclus.",
            "target_payment": "Requise pour calculer la durée.",
            "insurance_value": "Montant en devise si fixe, pourcentage si proportionnel.",
            "insurance_basis": "Utilisée uniquement pour une assurance en pourcentage.",
            "deferment_type": "Partiel : intérêts payés. Total : intérêts capitalisés.",
            "recurring_prepayment": "Le paiement normal est conservé afin de réduire la durée.",
        }
        widgets = {
            "currency": forms.TextInput(attrs={"maxlength": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        required = ("principal", "annual_rate", "calculation_mode", "start_date")
        if any(cleaned.get(field) is None for field in required):
            return cleaned
        try:
            calculate_loan(
                LoanAssumptions(
                    principal=cleaned["principal"],
                    annual_rate=cleaned["annual_rate"],
                    calculation_mode=cleaned["calculation_mode"],
                    duration_months=cleaned.get("duration_months"),
                    target_payment=cleaned.get("target_payment"),
                    insurance_mode=cleaned.get("insurance_mode"),
                    insurance_value=cleaned.get("insurance_value") or 0,
                    insurance_basis=cleaned.get("insurance_basis"),
                    initial_fees=cleaned.get("initial_fees") or 0,
                    deferment_months=cleaned.get("deferment_months") or 0,
                    deferment_type=cleaned.get("deferment_type"),
                    one_off_prepayment=cleaned.get("one_off_prepayment") or 0,
                    one_off_prepayment_month=cleaned.get("one_off_prepayment_month"),
                    recurring_prepayment=cleaned.get("recurring_prepayment") or 0,
                    recurring_prepayment_start_month=cleaned.get(
                        "recurring_prepayment_start_month"
                    ),
                    start_date=cleaned["start_date"],
                )
            )
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return cleaned


class CompoundInterestSimulationForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = CompoundInterestScenario
        exclude = ["user", "archived"]
        labels = {
            "name": "Nom du scénario",
            "initial_capital": "Capital initial",
            "periodic_contribution": "Versement périodique",
            "contribution_frequency": "Fréquence des versements",
            "contribution_timing": "Calendrier des versements",
            "duration_years": "Durée (années)",
            "annual_return": "Rendement nominal annuel (%)",
            "annual_fees": "Frais annuels (%)",
            "annual_inflation": "Inflation annuelle (%)",
            "tax_mode": "Fiscalité simplifiée",
            "tax_rate": "Taux fiscal sur les gains (%)",
            "start_date": "Date de départ",
        }
        help_texts = {
            "annual_return": "Taux nominal divisé en douze périodes mensuelles.",
            "annual_fees": "Prélevés mensuellement sur l'encours après rendement.",
            "tax_rate": "Appliqué uniquement aux gains positifs à la fin du scénario.",
        }
        widgets = {
            "currency": forms.TextInput(attrs={"maxlength": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        required = (
            "initial_capital",
            "periodic_contribution",
            "contribution_frequency",
            "contribution_timing",
            "duration_years",
            "annual_return",
            "annual_fees",
            "annual_inflation",
            "tax_mode",
            "tax_rate",
            "start_date",
        )
        if any(cleaned.get(field) is None for field in required):
            return cleaned
        try:
            calculate_compound_interest(
                CompoundInterestAssumptions(
                    initial_capital=cleaned["initial_capital"],
                    periodic_contribution=cleaned["periodic_contribution"],
                    contribution_frequency=cleaned["contribution_frequency"],
                    contribution_timing=cleaned["contribution_timing"],
                    duration_years=cleaned["duration_years"],
                    annual_return=cleaned["annual_return"],
                    annual_fees=cleaned["annual_fees"],
                    annual_inflation=cleaned["annual_inflation"],
                    tax_mode=cleaned["tax_mode"],
                    tax_rate=cleaned["tax_rate"],
                    start_date=cleaned["start_date"],
                )
            )
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return cleaned


class VirtualPortfolioForm(UserScopedFormMixin, TablerFormMixin, forms.ModelForm):
    class Meta:
        model = VirtualPortfolio
        fields = [
            "name",
            "base_currency",
            "initial_cash",
            "benchmark_instrument",
            "proportional_fee_rate",
            "fixed_fee",
            "spread_bps",
            "slippage_bps",
        ]
        labels = {
            "name": "Nom du portefeuille virtuel",
            "base_currency": "Devise de base",
            "initial_cash": "Capital virtuel initial",
            "benchmark_instrument": "Benchmark",
            "proportional_fee_rate": "Frais proportionnels (%)",
            "fixed_fee": "Frais fixes par ordre",
            "spread_bps": "Spread simulé (points de base)",
            "slippage_bps": "Slippage simulé (points de base)",
        }
        help_texts = {
            "benchmark_instrument": "Optionnel ; le cours doit utiliser la devise du portefeuille.",
            "spread_bps": "La moitié du spread est appliquée à chaque côté de l'ordre.",
            "slippage_bps": "Ajouté au prix d'achat et retranché du prix de vente.",
        }
        widgets = {"base_currency": forms.TextInput(attrs={"maxlength": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["benchmark_instrument"].queryset = Instrument.objects.filter(
            Q(owner=self.user) | Q(owner__isnull=True),
            status=Instrument.Status.ACTIVE,
        ).order_by("name", "ticker")
        if self.instance.pk:
            self.fields["base_currency"].disabled = True
            self.fields["initial_cash"].disabled = True


class VirtualOrderForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = VirtualOrder
        fields = ["instrument", "side", "order_type", "quantity", "limit_price"]
        labels = {
            "instrument": "Instrument de la watchlist",
            "side": "Sens",
            "order_type": "Type d'ordre",
            "quantity": "Quantité",
            "limit_price": "Cours limite",
        }
        help_texts = {
            "limit_price": "Laissez vide pour un ordre au marché.",
            "quantity": "Les fractions doivent être autorisées dans la watchlist.",
        }

    def __init__(self, *args, portfolio, **kwargs):
        self.portfolio = portfolio
        super().__init__(*args, **kwargs)
        self.fields["instrument"].queryset = Instrument.objects.filter(
            virtual_watchlist_entries__portfolio=portfolio,
            status=Instrument.Status.ACTIVE,
        ).distinct()

    def clean(self):
        cleaned = super().clean()
        instrument = cleaned.get("instrument")
        quantity = cleaned.get("quantity")
        if instrument is None or quantity is None:
            return cleaned
        entry = self.portfolio.watchlist_entries.filter(instrument=instrument).first()
        if entry is None:
            raise forms.ValidationError("L'instrument n'appartient pas à cette watchlist.")
        if not entry.allow_fractional and quantity != quantity.to_integral_value():
            self.add_error("quantity", "Cet instrument exige une quantité entière.")
        return cleaned


class VirtualWatchlistSettingsForm(TablerFormMixin, forms.Form):
    allow_fractional = forms.BooleanField(
        required=False,
        label="Autoriser les quantités fractionnaires",
    )

    def __init__(self, *args, instrument, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allow_fractional"].initial = default_fractional_permission(instrument)


class VirtualCorporateActionForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = VirtualCorporateAction
        fields = [
            "instrument",
            "action_type",
            "effective_at",
            "dividend_per_unit",
            "split_ratio",
        ]
        labels = {
            "instrument": "Instrument détenu",
            "action_type": "Événement",
            "effective_at": "Date et heure d'effet",
            "dividend_per_unit": "Dividende par unité",
            "split_ratio": "Ratio de division",
        }
        help_texts = {
            "split_ratio": "Exemple : 2 pour un split 2-pour-1.",
            "effective_at": "Un événement futur reste en attente.",
        }
        widgets = {
            "effective_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, portfolio, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instrument"].queryset = Instrument.objects.filter(
            virtual_positions__portfolio=portfolio,
            virtual_positions__quantity__gt=0,
        ).distinct()


class CloneVirtualPortfolioForm(TablerFormMixin, forms.Form):
    name = forms.CharField(max_length=255, label="Nom de la copie")


class ImportUploadForm(TablerFormMixin, forms.Form):
    file = forms.FileField(label="Fichier JSON ou Excel")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Le fichier ne doit pas dépasser 5 Mio.")
        suffix = upload.name.lower().rsplit(".", 1)[-1] if "." in upload.name else ""
        if suffix not in {"json", "xlsx"}:
            raise forms.ValidationError("Formats acceptés : .json et .xlsx.")
        return upload


class MarketDataPreferenceForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = MarketDataPreference
        fields = [
            "reporting_currency",
            "equity_display_currency",
            "crypto_display_currency",
            "benchmark_symbol",
        ]
        labels = {
            "reporting_currency": "Devise du patrimoine",
            "equity_display_currency": "Actions et ETF",
            "crypto_display_currency": "Cryptomonnaies",
            "benchmark_symbol": "Ticker Yahoo du benchmark",
        }
        help_texts = {
            "benchmark_symbol": "Exemple : ^STOXX50E pour l’EURO STOXX 50.",
        }

    def clean_benchmark_symbol(self):
        symbol = self.cleaned_data["benchmark_symbol"].strip().upper()
        if not symbol or len(symbol) > 30:
            raise forms.ValidationError("Renseignez un ticker de benchmark valide.")
        return symbol

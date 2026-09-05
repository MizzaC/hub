from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import ManualAccountForm, SubscriptionForm
from .models import (
    FREQUENCY_CHOICES,
    TRANSACTION_TYPES,
    Account,
    Connection,
    FinancialAuditEvent,
    Income,
    Instrument,
    MarketDataPreference,
    MarketDataStatus,
    Position,
    Subscription,
    Transaction,
)
from .services.audit import record_financial_event
from .services.dashboard import build_dashboard_performance, net_worth_snapshots
from .services.display_currency import prepare_currency_display
from .services.fx import ExchangeRateUnavailable, get_stored_rate
from .services.net_worth import build_portfolio_valuation
from .services.pricing import effective_price_state, latest_price
from .services.recurring import summarize_recurring


class FundBoardView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/fundboard.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super().get_context_data(**kwargs)
        accounts = Account.objects.filter(user=user, status=Account.Status.ACTIVE)
        preference, _ = MarketDataPreference.objects.get_or_create(user=user)
        valuation = build_portfolio_valuation(user, preference.reporting_currency)
        snapshots = net_worth_snapshots(user, preference.reporting_currency)
        performance = build_dashboard_performance(user, preference, snapshots)

        context["accounts_count"] = accounts.filter(
            category__in=["CURRENT", "SAVINGS"]
        ).count()
        context["investment_accounts_count"] = accounts.filter(
            category__in=["CTO", "PEA", "CRYPTO"]
        ).count()
        context["transactions_count"] = Transaction.objects.filter(user=user).count()
        context["positions_count"] = Position.objects.filter(account__user=user).count()
        context["subscriptions_count"] = Subscription.objects.filter(user=user).count()
        context["recent_transactions"] = (
            Transaction.objects.filter(user=user)
            .select_related("account")
            .order_by("-executed_at")[:5]
        )
        context["balance_totals"] = accounts.values("currency").annotate(
            total=Sum("balance")
        ).order_by("currency")
        context["connections_requiring_attention"] = Connection.objects.filter(
            user=user,
            status__in=[Connection.Status.STALE, Connection.Status.ERROR],
        ).count()
        market_statuses = list(
            MarketDataStatus.objects.filter(user=user).select_related("instrument")
        )
        for status in market_statuses:
            status.effective_state = (
                status.state
                if status.state == MarketDataStatus.State.ERROR
                else effective_price_state(status.instrument, latest_price(status.instrument))
            )
        try:
            fx_rate = get_stored_rate("EUR", "USD")
        except ExchangeRateUnavailable:
            fx_rate = None
        context.update(
            {
                "preference": preference,
                "valuation": valuation,
                "net_worth_snapshots": snapshots,
                "performance": performance,
                "fx_rate": fx_rate,
                "market_statuses": market_statuses,
                "market_attention_count": sum(
                    status.effective_state != MarketDataStatus.State.FRESH
                    for status in market_statuses
                ),
                "allocation_labels": [label for label, _ in valuation.allocation],
                "allocation_values": [str(value) for _, value in valuation.allocation],
                "history_labels": [item.observed_at.isoformat() for item in snapshots],
                "history_values": [str(item.converted_value) for item in snapshots],
            }
        )
        return context


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/portfolio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        investment_accounts = list(Account.objects.filter(
            user=self.request.user,
            status=Account.Status.ACTIVE,
            category__in=["CTO", "PEA", "CRYPTO"],
        ).prefetch_related("positions__instrument"))
        preference, _ = MarketDataPreference.objects.get_or_create(user=self.request.user)
        for account in investment_accounts:
            for position in account.positions.all():
                if position.current_value is None:
                    continue
                default_currency = (
                    preference.crypto_display_currency
                    if position.instrument.instrument_type == Instrument.Type.CRYPTO
                    else preference.equity_display_currency
                )
                position.market_display = prepare_currency_display(
                    position.current_value,
                    position.value_currency,
                    default_currency,
                )
        try:
            fx_rate = get_stored_rate("EUR", "USD")
        except ExchangeRateUnavailable:
            fx_rate = None
        context["investment_accounts"] = investment_accounts
        context["preference"] = preference
        context["fx_rate"] = fx_rate
        return context


class TransactionsView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "fundboard/transactions.html"
    context_object_name = "transactions"

    def get_queryset(self):
        return (
            Transaction.objects.filter(user=self.request.user)
            .select_related("account", "instrument")
            .order_by("-executed_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["accounts"] = Account.objects.filter(
            user=self.request.user,
            status=Account.Status.ACTIVE,
        )
        context["transaction_choices"] = TRANSACTION_TYPES
        return context


class SubscriptionsView(LoginRequiredMixin, ListView):
    model = Subscription
    template_name = "fundboard/subscriptions.html"
    context_object_name = "subscriptions"

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).order_by("next_due")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscriptions = list(context["subscriptions"])
        summary = summarize_recurring(subscriptions)

        context["subscriptions"] = subscriptions
        context["monthly_total"] = summary.monthly
        context["yearly_total"] = summary.yearly
        context["next_due"] = subscriptions[0].next_due if subscriptions else None

        labels_by_frequency = dict(FREQUENCY_CHOICES)
        aggregation = list(
            Subscription.objects.filter(user=self.request.user)
            .values("currency", "freq")
            .annotate(total=Sum("amount"))
            .order_by("currency", "freq")
        )
        context["chart_labels"] = [
            f"{labels_by_frequency[item['freq']]} · {item['currency']}" for item in aggregation
        ]
        context["chart_currencies"] = [item["currency"] for item in aggregation]
        # Numeric strings preserve Decimal values until JavaScript display conversion.
        context["chart_values"] = [format(item["total"], "f") for item in aggregation]
        return context


class RevenuesView(LoginRequiredMixin, ListView):
    model = Income
    template_name = "fundboard/revenues.html"
    context_object_name = "revenues"

    def get_queryset(self):
        return Income.objects.filter(user=self.request.user).order_by("next_payday")


class AccountsView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "fundboard/accounts.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user).select_related(
            "institution",
            "connection",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["manual_form"] = ManualAccountForm()
        return context


class AjaxModalMixin:
    template_name_fragment = None

    def dispatch(self, request, *args, **kwargs):
        if (
            request.method == "GET"
            and request.headers.get("x-requested-with") != "XMLHttpRequest"
        ):
            return HttpResponseForbidden("Modal uniquement.")
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        html = render_to_string(self.template_name_fragment, context, self.request)
        return HttpResponse(html, **response_kwargs)


class AccountSourceModal(LoginRequiredMixin, AjaxModalMixin, TemplateView):
    template_name_fragment = "fundboard/modals/account_source.html"


class AddAccountModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = "fundboard/modals/account_form.html"
    success_url = reverse_lazy("fundboard:accounts")

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.source = Account.Source.MANUAL
        response = super().form_valid(form)
        record_financial_event(
            self.request.user,
            FinancialAuditEvent.Type.MANUAL_CREATE,
            self.object,
        )
        messages.success(self.request, "Compte ajouté.")
        return response


class EditAccountModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = "fundboard/modals/account_form.html"
    success_url = reverse_lazy("fundboard:accounts")

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        record_financial_event(
            self.request.user,
            FinancialAuditEvent.Type.MANUAL_UPDATE,
            self.object,
        )
        messages.success(self.request, "Compte mis à jour.")
        return response


class DeleteAccountModal(LoginRequiredMixin, AjaxModalMixin, View):
    model = Account
    template_name_fragment = "fundboard/modals/account_delete.html"
    success_url = reverse_lazy("fundboard:accounts")

    def get_object(self):
        return get_object_or_404(
            Account.objects.filter(user=self.request.user),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        context = {"object": self.get_object()}
        return HttpResponse(render_to_string(self.template_name_fragment, context, request))

    def post(self, request, *args, **kwargs):
        account = self.get_object()
        account.status = Account.Status.ARCHIVED
        account.save(update_fields=["status", "updated_at"])
        record_financial_event(
            request.user,
            FinancialAuditEvent.Type.MANUAL_ARCHIVE,
            account,
            details={"field": "status", "value": Account.Status.ARCHIVED},
        )
        messages.success(request, "Compte archivé.")
        return redirect(self.success_url)


class AddSubscriptionModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name_fragment = "fundboard/modals/subscription_form.html"
    success_url = reverse_lazy("fundboard:subscriptions")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Abonnement ajouté.")
        return super().form_valid(form)


class EditSubscriptionModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name_fragment = "fundboard/modals/subscription_form.html"
    success_url = reverse_lazy("fundboard:subscriptions")

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Abonnement mis à jour.")
        return super().form_valid(form)


class DeleteSubscriptionModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    model = Subscription
    template_name_fragment = "fundboard/modals/subscription_delete.html"
    success_url = reverse_lazy("fundboard:subscriptions")

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Abonnement supprimé.")
        return super().form_valid(form)

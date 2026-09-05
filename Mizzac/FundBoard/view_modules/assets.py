"""Phase 7 detailed views and manual valuation histories."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from FundBoard.forms import (
    LoanBalanceSnapshotForm,
    PrivateEquityForm,
    PrivateEquityValuationForm,
    RealEstateValuationForm,
)
from FundBoard.models import (
    FinancialAuditEvent,
    Loan,
    LoanBalanceSnapshot,
    PrivateEquityHolding,
    PrivateEquityValuation,
    RealEstate,
    RealEstateValuation,
)
from FundBoard.services.asset_history import (
    record_loan_balance,
    record_private_equity_valuation,
    record_real_estate_valuation,
)
from FundBoard.services.assets import (
    loan_metrics,
    private_equity_metrics,
    real_estate_metrics,
    totals_by_currency,
)
from FundBoard.services.audit import record_financial_event

from .manual import ArchiveObjectModal, DynamicModalMixin, OwnedQueryMixin, UserFormMixin


class RealEstateDetailView(LoginRequiredMixin, OwnedQueryMixin, DetailView):
    model = RealEstate
    template_name = "fundboard/real_estate_detail.html"
    context_object_name = "property"

    def get_queryset(self):
        return super().get_queryset().select_related("linked_loan")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        valuations = list(self.object.valuations.order_by("valuation_date", "pk"))
        context.update(
            {
                "metrics": real_estate_metrics(self.object),
                "valuations": valuations,
                "chart_labels": [item.valuation_date.isoformat() for item in valuations],
                "chart_values": [format(item.value, "f") for item in valuations],
            }
        )
        return context


class LoanDetailView(LoginRequiredMixin, OwnedQueryMixin, DetailView):
    model = Loan
    template_name = "fundboard/loan_detail.html"
    context_object_name = "loan"

    def get_queryset(self):
        return super().get_queryset().select_related("account").prefetch_related("properties")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshots = list(self.object.balance_snapshots.order_by("observed_on", "pk"))
        context.update(
            {
                "metrics": loan_metrics(self.object),
                "snapshots": snapshots,
                "chart_labels": [item.observed_on.isoformat() for item in snapshots],
                "chart_values": [format(item.outstanding_principal, "f") for item in snapshots],
            }
        )
        return context


class PrivateEquityView(LoginRequiredMixin, ListView):
    model = PrivateEquityHolding
    template_name = "fundboard/private_equity.html"
    context_object_name = "holdings"

    def get_queryset(self):
        return PrivateEquityHolding.objects.filter(user=self.request.user).select_related("account")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        holdings = list(context["holdings"])
        for holding in holdings:
            holding.metrics = private_equity_metrics(holding)
        context["holdings"] = holdings
        context["totals"] = totals_by_currency(
            holdings,
            private_equity_metrics,
            ("commitment", "called_capital", "distributions", "net_asset_value"),
        )
        return context


class PrivateEquityDetailView(LoginRequiredMixin, OwnedQueryMixin, DetailView):
    model = PrivateEquityHolding
    template_name = "fundboard/private_equity_detail.html"
    context_object_name = "holding"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        valuations = list(self.object.valuations.order_by("valuation_date", "pk"))
        context.update(
            {
                "metrics": private_equity_metrics(self.object),
                "valuations": valuations,
                "chart_labels": [item.valuation_date.isoformat() for item in valuations],
                "chart_nav": [format(item.net_asset_value, "f") for item in valuations],
                "chart_called": [format(item.called_capital, "f") for item in valuations],
                "chart_distributions": [format(item.distributions, "f") for item in valuations],
            }
        )
        return context


class AddPrivateEquityModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    CreateView,
):
    model = PrivateEquityHolding
    form_class = PrivateEquityForm
    owner_field = "user"
    modal_title = "Ajouter une participation non cotée"
    success_message = "Participation ajoutée."

    def get_success_url(self):
        return reverse("fundboard:private_equity")

    def after_save(self, instance):
        record_private_equity_valuation(
            instance,
            net_asset_value=instance.net_asset_value,
            called_capital=instance.called_capital,
            distributions=instance.distributions,
            valuation_date=instance.valuation_date,
            source=instance.valuation_source,
        )


class EditPrivateEquityModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = PrivateEquityHolding
    form_class = PrivateEquityForm
    modal_title = "Modifier la participation"
    success_message = "Participation mise à jour."

    def get_success_url(self):
        return reverse("fundboard:private_equity_detail", args=[self.object.pk])

    def after_save(self, instance):
        record_private_equity_valuation(
            instance,
            net_asset_value=instance.net_asset_value,
            called_capital=instance.called_capital,
            distributions=instance.distributions,
            valuation_date=instance.valuation_date,
            source=instance.valuation_source,
        )


class ArchivePrivateEquityModal(ArchiveObjectModal):
    model = PrivateEquityHolding
    modal_title = "Archiver la participation"
    success_url = "fundboard:private_equity"


class RelatedHistoryCreateView(LoginRequiredMixin, DynamicModalMixin, CreateView):
    parent_model = None
    parent_url_name = ""
    relation_field = ""
    modal_title = "Ajouter une valorisation"

    def dispatch(self, request, *args, **kwargs):
        self.parent = get_object_or_404(
            self.parent_model,
            pk=kwargs["pk"],
            user=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(self.parent_url_name, args=[self.parent.pk])

    def audit(self, instance):
        record_financial_event(
            self.request.user,
            FinancialAuditEvent.Type.MANUAL_CREATE,
            instance,
        )


class AddRealEstateValuationModal(RelatedHistoryCreateView):
    model = RealEstateValuation
    form_class = RealEstateValuationForm
    parent_model = RealEstate
    parent_url_name = "fundboard:real_estate_detail"
    modal_title = "Ajouter une valorisation immobilière"

    def form_valid(self, form):
        snapshot = record_real_estate_valuation(
            self.parent,
            value=form.cleaned_data["value"],
            valuation_date=form.cleaned_data["valuation_date"],
            source=form.cleaned_data["source"],
        )
        self.audit(snapshot)
        messages.success(self.request, "Valorisation immobilière enregistrée.")
        return redirect(self.get_success_url())


class AddLoanBalanceModal(RelatedHistoryCreateView):
    model = LoanBalanceSnapshot
    form_class = LoanBalanceSnapshotForm
    parent_model = Loan
    parent_url_name = "fundboard:loan_detail"
    modal_title = "Actualiser le capital restant dû"

    def form_valid(self, form):
        snapshot = record_loan_balance(
            self.parent,
            outstanding_principal=form.cleaned_data["outstanding_principal"],
            observed_on=form.cleaned_data["observed_on"],
            source=form.cleaned_data["source"],
        )
        self.audit(snapshot)
        messages.success(self.request, "Capital restant dû enregistré.")
        return redirect(self.get_success_url())


class AddPrivateEquityValuationModal(RelatedHistoryCreateView):
    model = PrivateEquityValuation
    form_class = PrivateEquityValuationForm
    parent_model = PrivateEquityHolding
    parent_url_name = "fundboard:private_equity_detail"
    modal_title = "Ajouter une valorisation private equity"

    def form_valid(self, form):
        snapshot = record_private_equity_valuation(
            self.parent,
            net_asset_value=form.cleaned_data["net_asset_value"],
            called_capital=form.cleaned_data["called_capital"],
            distributions=form.cleaned_data["distributions"],
            valuation_date=form.cleaned_data["valuation_date"],
            source=form.cleaned_data["source"],
        )
        self.audit(snapshot)
        messages.success(self.request, "Valorisation private equity enregistrée.")
        return redirect(self.get_success_url())

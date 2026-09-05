from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from FundBoard.forms import (
    InstrumentForm,
    LoanForm,
    PositionForm,
    RealEstateForm,
    TransactionForm,
    UserScopedFormMixin,
)
from FundBoard.models import (
    FinancialAuditEvent,
    Instrument,
    Loan,
    Position,
    RealEstate,
    Transaction,
)
from FundBoard.services.asset_history import record_loan_balance, record_real_estate_valuation
from FundBoard.services.assets import loan_metrics, real_estate_metrics, totals_by_currency
from FundBoard.services.audit import record_financial_event


class DynamicModalMixin:
    template_name_fragment = "fundboard/modals/model_form.html"
    modal_title = "Saisie manuelle"
    submit_label = "Enregistrer"

    def dispatch(self, request, *args, **kwargs):
        if (
            request.method == "GET"
            and request.headers.get("x-requested-with") != "XMLHttpRequest"
        ):
            return HttpResponseForbidden("Modal uniquement.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["modal_title"] = self.modal_title
        context["submit_label"] = self.submit_label
        return context

    def render_to_response(self, context, **response_kwargs):
        html = render_to_string(self.template_name_fragment, context, self.request)
        return HttpResponse(html, **response_kwargs)


class UserFormMixin:
    owner_field = None
    success_message = "Enregistrement effectué."

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.owner_field and not getattr(form.instance, f"{self.owner_field}_id", None):
            setattr(form.instance, self.owner_field, self.request.user)
        return form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if issubclass(self.form_class, UserScopedFormMixin):
            kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        was_created = form.instance.pk is None
        if self.owner_field and not getattr(form.instance, f"{self.owner_field}_id", None):
            setattr(form.instance, self.owner_field, self.request.user)
        response = super().form_valid(form)
        self.after_save(form.instance)
        record_financial_event(
            self.request.user,
            (
                FinancialAuditEvent.Type.MANUAL_CREATE
                if was_created
                else FinancialAuditEvent.Type.MANUAL_UPDATE
            ),
            form.instance,
        )
        messages.success(self.request, self.success_message)
        return response

    def after_save(self, instance):
        return None


class OwnedQueryMixin:
    owner_lookup = "user"

    def get_queryset(self):
        return self.model.objects.filter(**{self.owner_lookup: self.request.user})


class InstrumentsView(LoginRequiredMixin, ListView):
    model = Instrument
    template_name = "fundboard/instruments.html"
    context_object_name = "instruments"

    def get_queryset(self):
        return Instrument.objects.filter(
            Q(owner=self.request.user) | Q(positions__account__user=self.request.user)
        ).exclude(manual_reference__startswith="system:benchmark:").distinct()


class AddInstrumentModal(LoginRequiredMixin, DynamicModalMixin, UserFormMixin, CreateView):
    model = Instrument
    form_class = InstrumentForm
    owner_field = "owner"
    modal_title = "Ajouter un instrument"
    success_message = "Instrument ajouté."
    success_url = reverse_lazy("fundboard:instruments")


class EditInstrumentModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = Instrument
    form_class = InstrumentForm
    owner_lookup = "owner"
    modal_title = "Modifier l’instrument"
    success_message = "Instrument mis à jour."
    success_url = reverse_lazy("fundboard:instruments")


class AddPositionModal(LoginRequiredMixin, DynamicModalMixin, UserFormMixin, CreateView):
    model = Position
    form_class = PositionForm
    modal_title = "Ajouter une position"
    success_message = "Position ajoutée."
    success_url = reverse_lazy("fundboard:portfolio")


class EditPositionModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = Position
    form_class = PositionForm
    owner_lookup = "account__user"
    modal_title = "Modifier la position"
    success_message = "Position mise à jour."
    success_url = reverse_lazy("fundboard:portfolio")


class AddTransactionModal(LoginRequiredMixin, DynamicModalMixin, UserFormMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    owner_field = "user"
    modal_title = "Ajouter une transaction"
    success_message = "Transaction ajoutée."
    success_url = reverse_lazy("fundboard:transactions")


class EditTransactionModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = Transaction
    form_class = TransactionForm
    modal_title = "Modifier la transaction"
    success_message = "Transaction mise à jour."
    success_url = reverse_lazy("fundboard:transactions")


class RealEstateView(LoginRequiredMixin, ListView):
    model = RealEstate
    template_name = "fundboard/real_estate.html"
    context_object_name = "properties"

    def get_queryset(self):
        return RealEstate.objects.filter(user=self.request.user).select_related("linked_loan")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        properties = list(context["properties"])
        for property_asset in properties:
            property_asset.metrics = real_estate_metrics(property_asset)
        context["properties"] = properties
        context["totals"] = totals_by_currency(
            properties,
            real_estate_metrics,
            ("gross_value", "remaining_debt", "net_value", "annual_net_income"),
        )
        context["has_incomplete_net_total"] = any(
            property_asset.metrics.net_value is None for property_asset in properties
        )
        return context


class AddRealEstateModal(LoginRequiredMixin, DynamicModalMixin, UserFormMixin, CreateView):
    model = RealEstate
    form_class = RealEstateForm
    owner_field = "user"
    modal_title = "Ajouter un bien immobilier"
    success_message = "Bien immobilier ajouté."
    success_url = reverse_lazy("fundboard:real_estate")

    def after_save(self, instance):
        record_real_estate_valuation(
            instance,
            value=instance.estimated_value,
            valuation_date=instance.valuation_date,
            source=instance.valuation_source,
        )


class EditRealEstateModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = RealEstate
    form_class = RealEstateForm
    modal_title = "Modifier le bien immobilier"
    success_message = "Bien immobilier mis à jour."
    success_url = reverse_lazy("fundboard:real_estate")

    def after_save(self, instance):
        record_real_estate_valuation(
            instance,
            value=instance.estimated_value,
            valuation_date=instance.valuation_date,
            source=instance.valuation_source,
        )


class LoansView(LoginRequiredMixin, ListView):
    model = Loan
    template_name = "fundboard/loans.html"
    context_object_name = "loans"

    def get_queryset(self):
        return Loan.objects.filter(user=self.request.user).select_related("account").prefetch_related(
            "properties"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loans = list(context["loans"])
        for loan in loans:
            loan.metrics = loan_metrics(loan)
        context["loans"] = loans
        return context


class AddLoanModal(LoginRequiredMixin, DynamicModalMixin, UserFormMixin, CreateView):
    model = Loan
    form_class = LoanForm
    owner_field = "user"
    modal_title = "Ajouter un prêt"
    success_message = "Prêt ajouté."
    success_url = reverse_lazy("fundboard:loans")

    def after_save(self, instance):
        record_loan_balance(
            instance,
            outstanding_principal=instance.outstanding_principal,
            observed_on=instance.balance_date,
            source="manual",
        )


class EditLoanModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = Loan
    form_class = LoanForm
    modal_title = "Modifier le prêt"
    success_message = "Prêt mis à jour."
    success_url = reverse_lazy("fundboard:loans")

    def after_save(self, instance):
        record_loan_balance(
            instance,
            outstanding_principal=instance.outstanding_principal,
            observed_on=instance.balance_date,
            source="manual",
        )


class ArchiveObjectModal(LoginRequiredMixin, DynamicModalMixin, View):
    template_name_fragment = "fundboard/modals/archive_confirm.html"
    model = None
    owner_lookup = "user"
    archive_field = "archived"
    archive_value = True
    modal_title = "Archiver"
    success_url = None
    success_message = "Élément archivé."

    def get_object(self):
        return get_object_or_404(
            self.model.objects.filter(**{self.owner_lookup: self.request.user}),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        context = {"object": self.get_object(), "modal_title": self.modal_title}
        return HttpResponse(render_to_string(self.template_name_fragment, context, request))

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        setattr(instance, self.archive_field, self.archive_value)
        instance.full_clean()
        instance.save(update_fields=[self.archive_field, "updated_at"])
        record_financial_event(
            request.user,
            FinancialAuditEvent.Type.MANUAL_ARCHIVE,
            instance,
            details={"field": self.archive_field, "value": str(self.archive_value)},
        )
        messages.success(request, self.success_message)
        return redirect(self.success_url)


class ArchiveInstrumentModal(ArchiveObjectModal):
    model = Instrument
    owner_lookup = "owner"
    archive_field = "status"
    archive_value = Instrument.Status.ARCHIVED
    modal_title = "Archiver l’instrument"
    success_url = "fundboard:instruments"


class ArchivePositionModal(ArchiveObjectModal):
    model = Position
    owner_lookup = "account__user"
    archive_field = "status"
    archive_value = Position.Status.ARCHIVED
    modal_title = "Archiver la position"
    success_url = "fundboard:portfolio"


class CancelTransactionModal(ArchiveObjectModal):
    model = Transaction
    archive_field = "status"
    archive_value = Transaction.Status.CANCELLED
    modal_title = "Annuler la transaction"
    success_url = "fundboard:transactions"
    success_message = "Transaction annulée."


class ArchiveRealEstateModal(ArchiveObjectModal):
    model = RealEstate
    modal_title = "Archiver le bien"
    success_url = "fundboard:real_estate"


class ArchiveLoanModal(ArchiveObjectModal):
    model = Loan
    modal_title = "Archiver le prêt"
    success_url = "fundboard:loans"

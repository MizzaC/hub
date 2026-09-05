"""Phase 9 virtual portfolio views with no real-order integration."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from FundBoard.exports.paper_trading import (
    virtual_portfolio_excel_bytes,
    virtual_portfolio_json_bytes,
)
from FundBoard.forms import (
    CloneVirtualPortfolioForm,
    VirtualCorporateActionForm,
    VirtualOrderForm,
    VirtualPortfolioForm,
    VirtualWatchlistSettingsForm,
)
from FundBoard.models import (
    FinancialAuditEvent,
    Instrument,
    VirtualCorporateAction,
    VirtualOrder,
    VirtualPortfolio,
    VirtualWatchlistEntry,
)
from FundBoard.services.audit import record_financial_event
from FundBoard.services.paper_trading import (
    add_to_virtual_watchlist,
    apply_virtual_corporate_action,
    cancel_virtual_order,
    clone_virtual_portfolio,
    create_virtual_snapshot,
    initialize_virtual_portfolio,
    latest_execution_price,
    place_virtual_order,
    process_open_virtual_orders,
    reset_virtual_portfolio,
    searchable_virtual_instruments,
    virtual_portfolio_valuation,
)

from .manual import ArchiveObjectModal, DynamicModalMixin, OwnedQueryMixin, UserFormMixin


class VirtualPortfolioListView(LoginRequiredMixin, ListView):
    model = VirtualPortfolio
    template_name = "fundboard/virtual_portfolios.html"
    context_object_name = "portfolios"

    def get_queryset(self):
        return VirtualPortfolio.objects.filter(
            user=self.request.user,
            archived=False,
        ).select_related("benchmark_instrument")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        portfolios = list(context["portfolios"])
        for portfolio in portfolios:
            portfolio.valuation = virtual_portfolio_valuation(portfolio)
        context["portfolios"] = portfolios
        return context


class VirtualPortfolioDetailView(LoginRequiredMixin, OwnedQueryMixin, DetailView):
    model = VirtualPortfolio
    template_name = "fundboard/virtual_portfolio_detail.html"
    context_object_name = "portfolio"

    def get_queryset(self):
        return super().get_queryset().select_related("benchmark_instrument")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        valuation = virtual_portfolio_valuation(self.object, as_of=now)
        watchlist = list(self.object.watchlist_entries.select_related("instrument"))
        for entry in watchlist:
            entry.latest_price = latest_execution_price(entry.instrument, as_of=now)
        query = self.request.GET.get("q", "")[:100]
        search_results = list(searchable_virtual_instruments(self.request.user, query)) if query else []
        snapshots = list(self.object.performance_snapshots.order_by("observed_at", "pk"))
        context.update(
            {
                "valuation": valuation,
                "watchlist": watchlist,
                "watched_instrument_ids": {entry.instrument_id for entry in watchlist},
                "query": query,
                "search_results": search_results,
                "orders": self.object.virtual_orders.select_related("instrument")[:50],
                "cash_events": self.object.cash_events.select_related("instrument")[:30],
                "corporate_actions": self.object.corporate_actions.select_related(
                    "instrument"
                )[:30],
                "snapshots": snapshots,
                "chart_labels": [item.observed_at.isoformat() for item in snapshots],
                "chart_values": [format(item.total_value, "f") for item in snapshots],
                "chart_benchmark": [
                    format(item.benchmark_value, "f") if item.benchmark_value is not None else None
                    for item in snapshots
                ],
            }
        )
        return context


class AddVirtualPortfolioModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    CreateView,
):
    model = VirtualPortfolio
    form_class = VirtualPortfolioForm
    owner_field = "user"
    modal_title = "Créer un portefeuille virtuel"
    success_message = "Portefeuille virtuel créé."

    def form_valid(self, form):
        form.instance.cash_balance = form.cleaned_data["initial_cash"]
        return super().form_valid(form)

    def after_save(self, instance):
        initialize_virtual_portfolio(instance)
        create_virtual_snapshot(instance)

    def get_success_url(self):
        return reverse("fundboard:virtual_portfolio_detail", args=[self.object.pk])


class EditVirtualPortfolioModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = VirtualPortfolio
    form_class = VirtualPortfolioForm
    modal_title = "Modifier le portefeuille virtuel"
    success_message = "Paramètres virtuels mis à jour."

    def after_save(self, instance):
        create_virtual_snapshot(instance)

    def get_success_url(self):
        return reverse("fundboard:virtual_portfolio_detail", args=[self.object.pk])


class ArchiveVirtualPortfolioModal(ArchiveObjectModal):
    model = VirtualPortfolio
    modal_title = "Archiver le portefeuille virtuel"
    success_url = "fundboard:virtual_portfolios"


class AddVirtualWatchlistModal(LoginRequiredMixin, DynamicModalMixin, FormView):
    form_class = VirtualWatchlistSettingsForm
    modal_title = "Ajouter à la watchlist virtuelle"

    def dispatch(self, request, *args, **kwargs):
        self.portfolio = get_object_or_404(
            VirtualPortfolio,
            pk=kwargs["pk"],
            user=request.user,
            archived=False,
        )
        self.instrument = get_object_or_404(
            Instrument.objects.filter(Q(owner=request.user) | Q(owner__isnull=True)),
            pk=kwargs["instrument_pk"],
            status=Instrument.Status.ACTIVE,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instrument"] = self.instrument
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"modal_title": self.modal_title, "submit_label": "Ajouter"})
        return context

    def form_valid(self, form):
        entry = add_to_virtual_watchlist(
            self.portfolio,
            self.instrument,
            allow_fractional=form.cleaned_data["allow_fractional"],
        )
        record_financial_event(
            self.request.user,
            FinancialAuditEvent.Type.MANUAL_CREATE,
            entry,
        )
        messages.success(self.request, "Instrument ajouté à la watchlist virtuelle.")
        return redirect("fundboard:virtual_portfolio_detail", pk=self.portfolio.pk)


class RemoveVirtualWatchlistView(LoginRequiredMixin, View):
    def post(self, request, pk, entry_pk):
        entry = get_object_or_404(
            VirtualWatchlistEntry.objects.select_related("portfolio"),
            pk=entry_pk,
            portfolio_id=pk,
            portfolio__user=request.user,
        )
        entry.delete()
        messages.success(request, "Instrument retiré de la watchlist.")
        return redirect("fundboard:virtual_portfolio_detail", pk=pk)


class PlaceVirtualOrderModal(LoginRequiredMixin, DynamicModalMixin, FormView):
    form_class = VirtualOrderForm
    modal_title = "Passer un ordre virtuel"

    def dispatch(self, request, *args, **kwargs):
        self.portfolio = get_object_or_404(
            VirtualPortfolio,
            pk=kwargs["pk"],
            user=request.user,
            archived=False,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["portfolio"] = self.portfolio
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"modal_title": self.modal_title, "submit_label": "Placer l'ordre"})
        return context

    def form_valid(self, form):
        try:
            order = place_virtual_order(
                self.portfolio,
                form.cleaned_data["instrument"],
                side=form.cleaned_data["side"],
                order_type=form.cleaned_data["order_type"],
                quantity=form.cleaned_data["quantity"],
                limit_price=form.cleaned_data.get("limit_price"),
            )
        except (PermissionError, ValueError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        record_financial_event(
            self.request.user,
            FinancialAuditEvent.Type.MANUAL_CREATE,
            order,
            details={"status": order.status},
        )
        if order.status == VirtualOrder.Status.EXECUTED:
            messages.success(self.request, "Ordre virtuel exécuté sur le cours local disponible.")
        elif order.status == VirtualOrder.Status.REJECTED:
            messages.error(self.request, f"Ordre virtuel rejeté : {order.status_message}")
        else:
            messages.info(self.request, f"Ordre virtuel ouvert : {order.status_message}")
        return redirect("fundboard:virtual_portfolio_detail", pk=self.portfolio.pk)


class ProcessVirtualOrdersView(LoginRequiredMixin, View):
    def post(self, request, pk):
        portfolio = get_object_or_404(
            VirtualPortfolio,
            pk=pk,
            user=request.user,
            archived=False,
        )
        results = process_open_virtual_orders(portfolio)
        executed = sum(order.status == VirtualOrder.Status.EXECUTED for order in results)
        messages.success(
            request,
            f"{executed} ordre(s) virtuel(s) exécuté(s) sur {len(results)} traité(s).",
        )
        return redirect("fundboard:virtual_portfolio_detail", pk=portfolio.pk)


class CancelVirtualOrderView(LoginRequiredMixin, View):
    def post(self, request, pk, order_pk):
        order = get_object_or_404(
            VirtualOrder.objects.select_related("portfolio"),
            pk=order_pk,
            portfolio_id=pk,
            portfolio__user=request.user,
        )
        try:
            cancel_virtual_order(order)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Ordre virtuel annulé.")
        return redirect("fundboard:virtual_portfolio_detail", pk=pk)


class AddVirtualCorporateActionModal(LoginRequiredMixin, DynamicModalMixin, FormView):
    form_class = VirtualCorporateActionForm
    modal_title = "Ajouter un événement virtuel"

    def dispatch(self, request, *args, **kwargs):
        self.portfolio = get_object_or_404(
            VirtualPortfolio,
            pk=kwargs["pk"],
            user=request.user,
            archived=False,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["portfolio"] = self.portfolio
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"modal_title": self.modal_title, "submit_label": "Enregistrer"})
        return context

    def form_valid(self, form):
        action = form.save(commit=False)
        action.portfolio = self.portfolio
        action.full_clean()
        action.save()
        apply_virtual_corporate_action(action)
        record_financial_event(
            self.request.user,
            FinancialAuditEvent.Type.MANUAL_CREATE,
            action,
        )
        messages.success(self.request, "Événement virtuel enregistré.")
        return redirect("fundboard:virtual_portfolio_detail", pk=self.portfolio.pk)


class ApplyVirtualCorporateActionView(LoginRequiredMixin, View):
    def post(self, request, pk, action_pk):
        action = get_object_or_404(
            VirtualCorporateAction.objects.select_related("portfolio"),
            pk=action_pk,
            portfolio_id=pk,
            portfolio__user=request.user,
        )
        result = apply_virtual_corporate_action(action)
        messages.info(request, result.status_message)
        return redirect("fundboard:virtual_portfolio_detail", pk=pk)


class CreateVirtualSnapshotView(LoginRequiredMixin, View):
    def post(self, request, pk):
        portfolio = get_object_or_404(VirtualPortfolio, pk=pk, user=request.user)
        create_virtual_snapshot(portfolio)
        messages.success(request, "Point de performance virtuel enregistré.")
        return redirect("fundboard:virtual_portfolio_detail", pk=pk)


class CloneVirtualPortfolioModal(LoginRequiredMixin, DynamicModalMixin, FormView):
    form_class = CloneVirtualPortfolioForm
    modal_title = "Cloner le portefeuille virtuel"

    def dispatch(self, request, *args, **kwargs):
        self.portfolio = get_object_or_404(VirtualPortfolio, pk=kwargs["pk"], user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"name": f"{self.portfolio.name} — copie"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"modal_title": self.modal_title, "submit_label": "Cloner"})
        return context

    def form_valid(self, form):
        try:
            clone = clone_virtual_portfolio(
                self.portfolio,
                name=form.cleaned_data["name"],
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Portefeuille virtuel cloné à son état courant.")
        return redirect("fundboard:virtual_portfolio_detail", pk=clone.pk)


class ResetVirtualPortfolioView(LoginRequiredMixin, DynamicModalMixin, View):
    template_name_fragment = "fundboard/modals/virtual_reset_confirm.html"

    def get_object(self):
        return get_object_or_404(
            VirtualPortfolio,
            pk=self.kwargs["pk"],
            user=self.request.user,
        )

    def get(self, request, *args, **kwargs):
        return HttpResponse(
            render_to_string(
                self.template_name_fragment,
                {"portfolio": self.get_object()},
                request,
            )
        )

    def post(self, request, *args, **kwargs):
        portfolio = self.get_object()
        reset_virtual_portfolio(portfolio)
        messages.success(request, "Portefeuille virtuel remis à son capital initial.")
        return redirect("fundboard:virtual_portfolio_detail", pk=portfolio.pk)


class VirtualPortfolioExportView(LoginRequiredMixin, View):
    def get(self, request, pk, file_format):
        portfolio = get_object_or_404(
            VirtualPortfolio.objects.select_related("benchmark_instrument"),
            pk=pk,
            user=request.user,
        )
        valuation = virtual_portfolio_valuation(portfolio)
        filename = slugify(portfolio.name) or f"portfolio-{portfolio.pk}"
        if file_format == "json":
            content = virtual_portfolio_json_bytes(portfolio, valuation)
            content_type = "application/json; charset=utf-8"
        elif file_format == "xlsx":
            content = virtual_portfolio_excel_bytes(portfolio, valuation)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            return HttpResponse("Format d'export inconnu.", status=400)
        record_financial_event(
            request.user,
            FinancialAuditEvent.Type.EXPORT,
            portfolio,
            details={"format": file_format, "resource": "virtual_portfolio"},
        )
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="mizzac-virtual-{filename}.{file_format}"'
        )
        return response

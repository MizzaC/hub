from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, RedirectView, TemplateView

from .forms import (
    BatchValuationFormSet,
    CollectionFilterForm,
    CollectibleValuationForm,
    CollectionOperationForm,
    OwnedLotCreateForm,
    ReportFilterForm,
)
from .models import Collectible, CollectibleValuation, CollectionOperation, OwnedLot, PokemonExtension, PokemonSeries
from .services import build_report_rows, build_market_snapshot, hydrate_lots_with_market_data, top_extensions_for_user


def apply_lot_filters(queryset, cleaned_data: dict, kind: str | None = None):
    if kind:
        queryset = queryset.filter(collectible__kind=kind)
    series = cleaned_data.get("series")
    extension = cleaned_data.get("extension")
    language = cleaned_data.get("language")
    is_graded = cleaned_data.get("is_graded")
    grading_company = cleaned_data.get("grading_company")
    card_condition = cleaned_data.get("card_condition")
    sealed_condition = cleaned_data.get("sealed_condition")
    product_type = cleaned_data.get("product_type")

    if series:
        queryset = queryset.filter(collectible__extension__series=series)
    if extension:
        queryset = queryset.filter(collectible__extension=extension)
    if language:
        queryset = queryset.filter(language=language)
    if is_graded == "1":
        queryset = queryset.filter(is_graded=True)
    elif is_graded == "0":
        queryset = queryset.filter(is_graded=False)
    if grading_company:
        queryset = queryset.filter(grading_company=grading_company)
    if card_condition:
        queryset = queryset.filter(card_condition=card_condition)
    if sealed_condition:
        queryset = queryset.filter(sealed_condition=sealed_condition)
    if product_type:
        queryset = queryset.filter(collectible__sealed_details__product_type=product_type)
    return queryset


def apply_operation_filters(queryset, cleaned_data: dict, kind: str | None = None):
    if kind:
        queryset = queryset.filter(lot__collectible__kind=kind)
    series = cleaned_data.get("series")
    extension = cleaned_data.get("extension")
    language = cleaned_data.get("language")
    is_graded = cleaned_data.get("is_graded")
    grading_company = cleaned_data.get("grading_company")
    card_condition = cleaned_data.get("card_condition")
    sealed_condition = cleaned_data.get("sealed_condition")
    product_type = cleaned_data.get("product_type")
    platform = cleaned_data.get("platform")

    if series:
        queryset = queryset.filter(lot__collectible__extension__series=series)
    if extension:
        queryset = queryset.filter(lot__collectible__extension=extension)
    if language:
        queryset = queryset.filter(lot__language=language)
    if is_graded == "1":
        queryset = queryset.filter(lot__is_graded=True)
    elif is_graded == "0":
        queryset = queryset.filter(lot__is_graded=False)
    if grading_company:
        queryset = queryset.filter(lot__grading_company=grading_company)
    if card_condition:
        queryset = queryset.filter(lot__card_condition=card_condition)
    if sealed_condition:
        queryset = queryset.filter(lot__sealed_condition=sealed_condition)
    if product_type:
        queryset = queryset.filter(lot__collectible__sealed_details__product_type=product_type)
    if platform:
        queryset = queryset.filter(Q(platform__icontains=platform) | Q(lot__platform__icontains=platform))
    return queryset


class PokeBoardMixin(LoginRequiredMixin):
    login_url = reverse_lazy("dashboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pokeboard_nav"] = [
            ("pokeboard:collection", "Collection"),
            ("pokeboard:dashboard", "Dashboard"),
            ("pokeboard:catalogue", "Catalogue"),
            ("pokeboard:report", "Report"),
            ("pokeboard:operations", "Historique"),
            ("pokeboard:valuations", "Valorisations"),
        ]
        ctx["collection_tabs"] = [
            ("cards", "Cartes", f"{reverse('pokeboard:collection')}?tab=cards"),
            ("sealed", "Scellés", f"{reverse('pokeboard:collection')}?tab=sealed"),
            ("revalue", "Valorisations à mettre à jour", reverse("pokeboard:stale_valuations")),
        ]
        return ctx


class PokeBoardDashboardView(PokeBoardMixin, TemplateView):
    template_name = "pokeboard/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lots = list(
            OwnedLot.objects.filter(user=self.request.user)
            .select_related(
                "collectible",
                "collectible__extension",
                "collectible__extension__series",
                "collectible__card_details",
                "collectible__sealed_details",
            )
            .order_by("collectible__name")
        )
        lots = hydrate_lots_with_market_data(lots)
        owned_lots = [lot for lot in lots if lot.remaining_quantity > 0]
        stale_threshold = timezone.now().date() - timedelta(days=90)
        stale_lots = [
            lot
            for lot in owned_lots
            if getattr(lot, "latest_valuation", None) is None or lot.latest_valuation.valued_at < stale_threshold
        ]
        total_purchase = sum((lot.acquisition_total for lot in owned_lots), Decimal("0"))
        total_current = sum((lot.current_total_value or Decimal("0") for lot in owned_lots), Decimal("0"))
        total_unrealized = sum((lot.unrealized_pnl or Decimal("0") for lot in owned_lots), Decimal("0"))
        total_realized = sum((lot.realized_pnl_total for lot in lots), Decimal("0"))

        ctx.update(
            lots_count=len(owned_lots),
            stale_lots_count=len(stale_lots),
            total_purchase=total_purchase,
            total_current=total_current,
            total_unrealized=total_unrealized,
            total_realized=total_realized,
            stale_lots=stale_lots[:5],
            recent_operations=CollectionOperation.objects.filter(user=self.request.user)
            .select_related(
                "lot",
                "lot__collectible",
                "lot__collectible__extension",
                "lot__collectible__extension__series",
            )
            .order_by("-operation_date", "-id")[:8],
            top_extensions=top_extensions_for_user(self.request.user),
        )
        return ctx


class CollectionView(PokeBoardMixin, TemplateView):
    template_name = "pokeboard/collection.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "cards")
        if tab not in {"cards", "sealed"}:
            tab = "cards"
        filter_form = CollectionFilterForm(self.request.GET or None)
        queryset = (
            OwnedLot.objects.filter(user=self.request.user, remaining_quantity__gt=0)
            .select_related(
                "collectible",
                "collectible__extension",
                "collectible__extension__series",
                "collectible__card_details",
                "collectible__sealed_details",
            )
            .order_by("collectible__extension__series__era_order", "collectible__extension__name", "collectible__name")
        )
        if filter_form.is_valid():
            queryset = apply_lot_filters(queryset, filter_form.cleaned_data, kind="CARD" if tab == "cards" else "SEALED")
        else:
            queryset = queryset.filter(collectible__kind="CARD" if tab == "cards" else "SEALED")

        lots = hydrate_lots_with_market_data(list(queryset))
        ctx.update(
            active_collection_tab=tab,
            filter_form=filter_form,
            lots=lots,
            cards_tab_url=f"{reverse('pokeboard:collection')}?tab=cards",
            sealed_tab_url=f"{reverse('pokeboard:collection')}?tab=sealed",
            revalue_tab_url=reverse("pokeboard:stale_valuations"),
        )
        return ctx


class StaleValuationUpdateView(PokeBoardMixin, TemplateView):
    template_name = "pokeboard/stale_valuations.html"

    def _build_lots(self, include_fresh: bool):
        filter_form = CollectionFilterForm(self.request.GET or None)
        queryset = (
            OwnedLot.objects.filter(user=self.request.user, remaining_quantity__gt=0)
            .select_related(
                "collectible",
                "collectible__extension",
                "collectible__extension__series",
                "collectible__card_details",
                "collectible__sealed_details",
            )
            .order_by("collectible__extension__series__era_order", "collectible__extension__name", "collectible__name")
        )
        if filter_form.is_valid():
            queryset = apply_lot_filters(queryset, filter_form.cleaned_data)

        lots = hydrate_lots_with_market_data(list(queryset))
        threshold = timezone.now().date() - timedelta(days=90)
        visible_lots = []
        for lot in lots:
            valuation = getattr(lot, "latest_valuation", None)
            lot.needs_valuation = valuation is None or valuation.valued_at < threshold
            lot.days_since_valuation = None if valuation is None else (timezone.now().date() - valuation.valued_at).days
            if include_fresh or lot.needs_valuation:
                visible_lots.append(lot)
        return filter_form, visible_lots

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        include_fresh = self.request.GET.get("scope") == "all"
        filter_form, lots = self._build_lots(include_fresh)
        formset = kwargs.get("formset")
        if formset is None:
            initial = [
                {
                    "lot_id": lot.id,
                    "valued_at": timezone.now().date(),
                    "next_url": self.request.get_full_path(),
                }
                for lot in lots
            ]
            formset = BatchValuationFormSet(initial=initial)
        for form, lot in zip(formset.forms, lots):
            form.lot = lot
        ctx.update(
            active_collection_tab="revalue",
            filter_form=filter_form,
            lots=lots,
            formset=formset,
            include_fresh=include_fresh,
            cards_tab_url=f"{reverse('pokeboard:collection')}?tab=cards",
            sealed_tab_url=f"{reverse('pokeboard:collection')}?tab=sealed",
            revalue_tab_url=reverse("pokeboard:stale_valuations"),
        )
        return ctx

    def post(self, request, *args, **kwargs):
        include_fresh = request.GET.get("scope") == "all"
        filter_form, lots = self._build_lots(include_fresh)
        formset = BatchValuationFormSet(request.POST)
        created_count = 0
        if formset.is_valid():
            lot_map = {lot.id: lot for lot in lots}
            for form in formset:
                unit_value = form.cleaned_data.get("unit_value")
                lot_id = form.cleaned_data.get("lot_id")
                if unit_value in (None, "") or lot_id not in lot_map:
                    continue
                lot = lot_map[lot_id]
                defaults = {
                    "unit_value": unit_value,
                    "notes": "",
                }
                CollectibleValuation.objects.update_or_create(
                    collectible=lot.collectible,
                    kind=lot.collectible.kind,
                    language=lot.language,
                    card_condition=lot.card_condition if not lot.is_graded else None,
                    is_graded=lot.is_graded,
                    grading_company=lot.grading_company if lot.is_graded else None,
                    grading_grade=lot.grading_grade if lot.is_graded else None,
                    sealed_condition=lot.sealed_condition if lot.is_sealed else None,
                    valued_at=form.cleaned_data.get("valued_at") or timezone.now().date(),
                    source_type="MANUAL",
                    defaults=defaults,
                )
                created_count += 1
            messages.success(request, f"{created_count} valorisation(s) enregistrée(s).")
            return HttpResponseRedirect(request.get_full_path())

        messages.error(request, "Impossible d'enregistrer certaines valorisations.")
        for form, lot in zip(formset.forms, lots):
            form.lot = lot
        return self.render_to_response(
            self.get_context_data(formset=formset, filter_form=filter_form, lots=lots, include_fresh=include_fresh)
        )


class CatalogueView(PokeBoardMixin, TemplateView):
    template_name = "pokeboard/catalogue.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["series_list"] = PokemonSeries.objects.prefetch_related(
            Prefetch("extensions", queryset=PokemonExtension.objects.order_by("release_date", "name"))
        )
        ctx["collectibles"] = Collectible.objects.select_related(
            "extension", "extension__series", "card_details", "sealed_details"
        ).order_by("extension__series__era_order", "extension__name", "name")[:100]
        return ctx


class OperationsView(PokeBoardMixin, ListView):
    template_name = "pokeboard/operations.html"
    context_object_name = "operations"
    paginate_by = 50

    def get_queryset(self):
        queryset = (
            CollectionOperation.objects.filter(user=self.request.user)
            .select_related(
                "lot",
                "lot__collectible",
                "lot__collectible__extension",
                "lot__collectible__extension__series",
                "lot__collectible__card_details",
                "lot__collectible__sealed_details",
            )
            .order_by("-operation_date", "-id")
        )
        self.target_lot = None
        lot_id = self.request.GET.get("lot")
        if lot_id:
            self.target_lot = get_object_or_404(OwnedLot, pk=lot_id, user=self.request.user)
            queryset = queryset.filter(lot=self.target_lot)
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target_lot"] = self.target_lot
        return ctx


class ReportView(PokeBoardMixin, TemplateView):
    template_name = "pokeboard/report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filter_form = ReportFilterForm(self.request.GET or None)
        operations = (
            CollectionOperation.objects.filter(user=self.request.user)
            .select_related(
                "lot",
                "lot__collectible",
                "lot__collectible__extension",
                "lot__collectible__extension__series",
                "lot__collectible__card_details",
                "lot__collectible__sealed_details",
            )
            .order_by("-operation_date", "-id")
        )

        if filter_form.is_valid():
            kind = filter_form.cleaned_data.get("kind") or None
            operations = apply_operation_filters(operations, filter_form.cleaned_data, kind=kind)

        rows = build_report_rows(list(operations))
        ctx.update(filter_form=filter_form, rows=rows)
        return ctx


class ValuationsView(PokeBoardMixin, ListView):
    template_name = "pokeboard/valuations.html"
    context_object_name = "valuations"
    paginate_by = 50

    def get_queryset(self):
        queryset = (
            CollectibleValuation.objects.filter(collectible__lots__user=self.request.user)
            .select_related("collectible", "collectible__extension", "collectible__extension__series")
            .distinct()
            .order_by("-valued_at", "-id")
        )
        self.target_lot = None
        lot_id = self.request.GET.get("lot")
        if lot_id:
            self.target_lot = get_object_or_404(OwnedLot, pk=lot_id, user=self.request.user)
            queryset = queryset.filter(
                collectible=self.target_lot.collectible,
                kind=self.target_lot.collectible.kind,
                language=self.target_lot.language,
                card_condition=self.target_lot.card_condition if not self.target_lot.is_graded else None,
                is_graded=self.target_lot.is_graded,
                grading_company=self.target_lot.grading_company if self.target_lot.is_graded else None,
                grading_grade=self.target_lot.grading_grade if self.target_lot.is_graded else None,
                sealed_condition=self.target_lot.sealed_condition if self.target_lot.is_sealed else None,
            )
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target_lot"] = self.target_lot
        return ctx


class OwnedLotCreateView(PokeBoardMixin, FormView):
    template_name = "pokeboard/lot_form.html"
    form_class = OwnedLotCreateForm
    success_url = reverse_lazy("pokeboard:collection")

    def get_success_url(self):
        return self.request.POST.get("next_url") or self.request.GET.get("next") or str(self.success_url)

    def get_initial(self):
        initial = super().get_initial()
        kind = self.request.GET.get("kind")
        if kind in {"CARD", "SEALED"}:
            initial["kind"] = kind
        return initial

    def form_valid(self, form):
        form.save(self.request.user)
        messages.success(self.request, "Element ajouté à la collection.")
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["return_url"] = self.request.POST.get("next_url") or self.request.GET.get("next") or reverse("pokeboard:collection")
        return ctx


class CollectionOperationCreateView(PokeBoardMixin, FormView):
    template_name = "pokeboard/operation_form.html"
    form_class = CollectionOperationForm
    success_url = reverse_lazy("pokeboard:operations")

    def _get_lot(self):
        lot_id = self.request.GET.get("lot") or self.request.POST.get("lot")
        if not lot_id:
            return None
        return get_object_or_404(OwnedLot, pk=lot_id, user=self.request.user)

    def get_form(self, form_class=None):
        return CollectionOperationForm(
            self.request.user,
            **self.get_form_kwargs(),
            lot=self._get_lot(),
        )

    def get_success_url(self):
        return self.request.POST.get("next_url") or self.request.GET.get("next") or str(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target_lot"] = self._get_lot()
        ctx["return_url"] = self.request.POST.get("next_url") or self.request.GET.get("next") or reverse("pokeboard:operations")
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Operation enregistrée.")
        return HttpResponseRedirect(self.get_success_url())


class CollectibleValuationCreateView(PokeBoardMixin, FormView):
    template_name = "pokeboard/valuation_form.html"
    form_class = CollectibleValuationForm
    success_url = reverse_lazy("pokeboard:valuations")

    def _get_lot(self):
        lot_id = self.request.GET.get("lot") or self.request.POST.get("lot")
        if not lot_id:
            return None
        return get_object_or_404(OwnedLot, pk=lot_id, user=self.request.user)

    def get_form(self, form_class=None):
        return CollectibleValuationForm(
            **self.get_form_kwargs(),
            lot=self._get_lot(),
        )

    def get_success_url(self):
        return self.request.POST.get("next_url") or self.request.GET.get("next") or str(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target_lot"] = self._get_lot()
        ctx["return_url"] = self.request.POST.get("next_url") or self.request.GET.get("next") or reverse("pokeboard:valuations")
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Valorisation enregistrée.")
        return HttpResponseRedirect(self.get_success_url())


class PositionsRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return f"{reverse('pokeboard:collection')}?tab=cards"

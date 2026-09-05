"""Authenticated market-data, settings and detail views."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, TemplateView

from FundBoard.forms import MarketDataPreferenceForm
from FundBoard.integrations.market_data.base import MarketDataError
from FundBoard.integrations.market_data.registry import provider_name_for
from FundBoard.models import (
    Account,
    FinancialAuditEvent,
    Instrument,
    MarketDataPreference,
    MarketDataStatus,
    Position,
    Snapshot,
)
from FundBoard.services.audit import record_financial_event
from FundBoard.services.display_currency import prepare_currency_display
from FundBoard.services.fx import ExchangeRateUnavailable, get_stored_rate, refresh_exchange_rate
from FundBoard.services.pricing import (
    effective_price_state,
    ensure_benchmark_instrument,
    refresh_instrument_market_data,
)
from FundBoard.services.snapshots import IncompleteValuationError, create_daily_snapshots


def _preference(user):
    preference, _ = MarketDataPreference.objects.get_or_create(user=user)
    return preference


def _instrument_queryset(user):
    return Instrument.objects.filter(
        Q(owner=user) | Q(owner__isnull=True, positions__account__user=user)
    ).distinct()


def _fx_rate_or_none():
    try:
        return get_stored_rate("EUR", "USD")
    except ExchangeRateUnavailable:
        return None


class MarketSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/market_settings.html"

    def get(self, request, *args, **kwargs):
        preference = _preference(request.user)
        return self.render_to_response({"form": MarketDataPreferenceForm(instance=preference)})

    def post(self, request, *args, **kwargs):
        preference = _preference(request.user)
        previous_symbol = preference.benchmark_symbol
        form = MarketDataPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            preference = form.save(commit=False)
            if preference.benchmark_symbol != previous_symbol:
                preference.benchmark_instrument = None
            preference.full_clean()
            preference.save()
            record_financial_event(
                request.user,
                FinancialAuditEvent.Type.SETTINGS_UPDATE,
                preference,
                details={
                    "reporting_currency": preference.reporting_currency,
                    "equity_display_currency": preference.equity_display_currency,
                    "crypto_display_currency": preference.crypto_display_currency,
                    "benchmark_symbol": preference.benchmark_symbol,
                },
            )
            messages.success(request, "Préférences de marché enregistrées.")
            return redirect("fundboard:market_settings")
        return self.render_to_response({"form": form}, status=400)


class RefreshFxView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            rates = refresh_exchange_rate("EUR", "USD")
        except MarketDataError:
            messages.error(
                request,
                "Frankfurter/ECB est indisponible. Le dernier taux enregistré reste utilisé.",
            )
        else:
            record_financial_event(
                request.user,
                FinancialAuditEvent.Type.FX_REFRESH,
                details={
                    "pair": "EUR/USD",
                    "rate_date": rates[0].rate_date.isoformat(),
                    "source": rates[0].source,
                },
            )
            messages.success(request, "Taux EUR/USD Frankfurter/ECB actualisé.")
        return redirect("fundboard:fundboard")


class RefreshInstrumentView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        instrument = get_object_or_404(_instrument_queryset(request.user), pk=pk)
        try:
            price, positions_updated, history_count = refresh_instrument_market_data(
                request.user,
                instrument,
            )
        except MarketDataError:
            messages.error(
                request,
                "Le fournisseur est indisponible. Le dernier cours connu est conservé.",
            )
        else:
            record_financial_event(
                request.user,
                FinancialAuditEvent.Type.MARKET_REFRESH,
                instrument,
                details={
                    "source": price.source,
                    "observed_at": price.observed_at.isoformat(),
                    "positions_updated": positions_updated,
                    "history_points": history_count,
                },
            )
            messages.success(request, "Cours et historique actualisés.")
        return redirect("fundboard:instrument_detail", pk=instrument.pk)


class RefreshBenchmarkView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        preference = _preference(request.user)
        instrument = ensure_benchmark_instrument(preference)
        try:
            price, _, history_count = refresh_instrument_market_data(
                request.user,
                instrument,
            )
        except MarketDataError:
            messages.error(
                request,
                "Le benchmark n’a pas pu être actualisé. Son historique est conservé.",
            )
        else:
            record_financial_event(
                request.user,
                FinancialAuditEvent.Type.MARKET_REFRESH,
                instrument,
                details={
                    "benchmark": preference.benchmark_symbol,
                    "source": price.source,
                    "history_points": history_count,
                },
            )
            messages.success(request, "Benchmark actualisé.")
        return redirect("fundboard:fundboard")


class CreateSnapshotView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            result = create_daily_snapshots(request.user)
        except IncompleteValuationError as exc:
            messages.error(
                request,
                f"Snapshot non créé : {len(exc.issues)} valorisation(s) incomplète(s).",
            )
        else:
            record_financial_event(
                request.user,
                FinancialAuditEvent.Type.SNAPSHOT,
                details={
                    "created": result.created,
                    "existing": result.existing,
                    "observed_at": result.observed_at.isoformat(),
                },
            )
            if result.created:
                messages.success(request, "Snapshot patrimonial du jour créé.")
            else:
                messages.info(request, "Le snapshot patrimonial du jour existe déjà.")
        return redirect("fundboard:fundboard")


class InstrumentDetailView(LoginRequiredMixin, DetailView):
    model = Instrument
    template_name = "fundboard/instrument_detail.html"
    context_object_name = "instrument"

    def get_queryset(self):
        return _instrument_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instrument = context["instrument"]
        preference = _preference(self.request.user)
        prices = list(reversed(list(instrument.prices.order_by("-observed_at")[:1000])))
        latest = prices[-1] if prices else None
        positions = list(
            Position.objects.filter(account__user=self.request.user, instrument=instrument)
            .select_related("account")
            .order_by("account__name")
        )
        default_currency = (
            preference.crypto_display_currency
            if instrument.instrument_type == Instrument.Type.CRYPTO
            else preference.equity_display_currency
        )
        for position in positions:
            if position.current_value is not None:
                position.market_display = prepare_currency_display(
                    position.current_value,
                    position.value_currency,
                    default_currency,
                )
        provider_name = provider_name_for(instrument)
        status = MarketDataStatus.objects.filter(
            user=self.request.user,
            instrument=instrument,
            provider=provider_name,
        ).first()
        context.update(
            {
                "preference": preference,
                "positions": positions,
                "latest_price": latest,
                "effective_state": effective_price_state(instrument, latest),
                "market_status": status,
                "provider_name": provider_name,
                "price_chart_labels": [price.observed_at.isoformat() for price in prices],
                "price_chart_values": [str(price.close_price) for price in prices],
                "fx_rate": _fx_rate_or_none(),
            }
        )
        return context


class AccountDetailView(LoginRequiredMixin, DetailView):
    model = Account
    template_name = "fundboard/account_detail.html"
    context_object_name = "account"

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = context["account"]
        preference = _preference(self.request.user)
        positions = list(account.positions.select_related("instrument"))
        for position in positions:
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
        snapshots = list(
            Snapshot.objects.filter(
                user=self.request.user,
                account=account,
                scope=Snapshot.Scope.ACCOUNT,
            ).order_by("observed_at")
        )
        context.update(
            {
                "positions": positions,
                "snapshots": snapshots,
                "snapshot_labels": [item.observed_at.isoformat() for item in snapshots],
                "snapshot_values": [str(item.converted_value) for item in snapshots],
                "transactions": account.transactions.order_by("-executed_at")[:20],
                "fx_rate": _fx_rate_or_none(),
            }
        )
        return context

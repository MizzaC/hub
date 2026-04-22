from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.http import urlencode
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
)

from .forms import ExpenseForm, IncomeForm, ManualAccountForm, MarkIncomeForm
from .ledger.services import LegInput, post_transaction
from .models import Account, Asset, CashflowRule, Holding, Leg, Transaction


def month_bounds(d: date) -> tuple[date, date]:
    first = d.replace(day=1)
    next_month_first = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first, next_month_first - timedelta(days=1)


def last_n_month_starts(n: int, ref: date | None = None) -> list[date]:
    ref = ref or date.today()
    first_this, _ = month_bounds(ref)
    months: list[date] = []
    y, m = first_this.year, first_this.month
    for _ in range(n):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y -= 1
            m = 12
    months.reverse()
    return months


def dec_to_float(d: Decimal | None) -> float:
    return float(d or Decimal("0"))


def parse_ym(request, fallback_date: date) -> date:
    ym = request.GET.get("ym")
    if ym:
        try:
            y, m = ym.split("-")
            return date(int(y), int(m), 1)
        except Exception:
            pass
    return fallback_date.replace(day=1)


def ym_str(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_is_active_for(rule: CashflowRule, month_start: date, month_end: date) -> bool:
    if rule.start_date and rule.start_date > month_end:
        return False
    if rule.end_date and rule.end_date < month_start:
        return False
    return True


def _rule_list_for_period(user, kind: str, month_start: date, month_end: date):
    return CashflowRule.objects.filter(user=user, kind=kind).filter(
        start_date__lte=month_end
    ).exclude(end_date__lt=month_start)


def month_total_recurring_rules(user, kind: str, month_start: date, month_end: date) -> Decimal:
    qs = _rule_list_for_period(user, kind, month_start, month_end).filter(is_recurring=True)
    return sum((r.monthly_equivalent() for r in qs), Decimal("0"))


def month_total_onetime_rules(user, kind: str, month_start: date, month_end: date) -> Decimal:
    return (
        _rule_list_for_period(user, kind, month_start, month_end)
        .filter(is_recurring=False, next_due__range=(month_start, month_end))
        .aggregate(s=Sum("amount"))["s"]
        or Decimal("0")
    )


def month_rule_split(user, kind: str, month_start: date, month_end: date) -> tuple[dict[str, Decimal], Decimal]:
    split: dict[str, Decimal] = {}
    recurring = _rule_list_for_period(user, kind, month_start, month_end).filter(is_recurring=True)
    one_time = _rule_list_for_period(user, kind, month_start, month_end).filter(
        is_recurring=False, next_due__range=(month_start, month_end)
    )

    for rule in recurring:
        key = rule.tag or rule.name or "Autre"
        split[key] = split.get(key, Decimal("0")) + rule.monthly_equivalent()
    for rule in one_time:
        key = rule.tag or rule.name or "Autre"
        split[key] = split.get(key, Decimal("0")) + (rule.amount or Decimal("0"))

    return split, sum(split.values(), Decimal("0"))


def _decorate_transaction(tx: Transaction) -> Transaction:
    legs = list(tx.legs.all())
    tx.date_trx = tx.executed_at
    tx.amount = sum((leg.value_reference for leg in legs), Decimal("0"))
    tx.account = legs[0].account if legs else None
    asset_leg = next((leg for leg in legs if leg.asset.asset_type != "FIAT"), legs[0] if legs else None)
    tx.asset = asset_leg.asset if asset_leg else None
    tx.quantity = asset_leg.quantity if asset_leg else None
    return tx


def _period_leg_totals(user, month_start: date, month_end: date) -> tuple[Decimal, Decimal]:
    legs = Leg.objects.filter(
        transaction__user=user,
        transaction__executed_at__date__range=(month_start, month_end),
    )
    total_in = sum((leg.value_reference for leg in legs if leg.value_reference > 0), Decimal("0"))
    total_out = sum((-leg.value_reference for leg in legs if leg.value_reference < 0), Decimal("0"))
    return total_in, total_out


class FundBoardView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/fundboard.html"
    login_url = reverse_lazy("fundboard:login")

    def get_context_data(self, **kwargs):
        user = self.request.user
        ctx = super().get_context_data(**kwargs)

        accounts_qs = Account.objects.filter(user=user)
        accounts_count = accounts_qs.count()
        investment_accounts_count = accounts_qs.filter(category__in=["CTO", "PEA", "CRYPTO"]).count()

        account_balances = (
            Leg.objects.filter(transaction__user=user)
            .values("account_id")
            .annotate(total=Sum("value_reference"))
        )
        total_balance = sum((row["total"] or Decimal("0") for row in account_balances), Decimal("0"))

        tx_qs = (
            Transaction.objects.filter(user=user)
            .prefetch_related("legs__account", "legs__asset")
            .order_by("-executed_at")
        )
        recent_transactions = [_decorate_transaction(tx) for tx in tx_qs[:5]]

        month_start, month_end = month_bounds(date.today())
        period_label = month_start.strftime("%B %Y").capitalize()
        cat_map, total_out = month_rule_split(user, "EXPENSE", month_start, month_end)
        total_in, _ = _period_leg_totals(user, month_start, month_end)

        ctx.update(
            accounts_count=accounts_count,
            investment_accounts_count=investment_accounts_count,
            transactions_count=tx_qs.count(),
            subscriptions_count=CashflowRule.objects.filter(user=user, kind="EXPENSE", is_recurring=True).count(),
            recent_transactions=recent_transactions,
            total_balance=total_balance,
            active_period_label=f"{month_start:%d/%m/%Y} -> {month_end:%d/%m/%Y}",
            donut_labels_json=json.dumps(list(cat_map.keys()), ensure_ascii=False),
            donut_data_json=json.dumps([dec_to_float(v) for v in cat_map.values()], ensure_ascii=False),
            in_out_labels_json=json.dumps(["Entrees", "Sorties"], ensure_ascii=False),
            in_out_values_json=json.dumps([dec_to_float(total_in), dec_to_float(total_out)], ensure_ascii=False),
            cf_links_json=json.dumps(
                [{"from": "Entrees", "to": tag, "flow": dec_to_float(amount)} for tag, amount in cat_map.items()],
                ensure_ascii=False,
            ),
            cashflow_period_label=period_label,
            inout_period_label=period_label,
        )
        return ctx


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/assets.html"
    login_url = reverse_lazy("fundboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["holdings"] = Holding.objects.filter(user=self.request.user).select_related("account", "asset")
        return ctx


class TransactionsView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "fundboard/transactions.html"
    context_object_name = "transactions"
    login_url = reverse_lazy("fundboard:login")

    def get_queryset(self):
        qs = (
            Transaction.objects.filter(user=self.request.user)
            .prefetch_related("legs__account", "legs__asset")
            .order_by("-executed_at")
        )
        return [_decorate_transaction(tx) for tx in qs]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["accounts"] = Account.objects.filter(user=self.request.user).order_by("name")
        ctx["transaction_choices"] = Transaction._meta.get_field("trx_type").choices
        return ctx


class ExpensesView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/expenses.html"
    login_url = reverse_lazy("fundboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        base_today = date.today()
        month_first = parse_ym(self.request, base_today)
        month_start, month_end = month_bounds(month_first)
        prev_month_first = (month_start - timedelta(days=1)).replace(day=1)
        next_month_first = (month_end + timedelta(days=1)).replace(day=1)
        period_label = month_start.strftime("%B %Y").capitalize()

        recurring_qs = CashflowRule.objects.filter(user=user, kind="EXPENSE", is_recurring=True).order_by("next_due")
        one_time_qs = CashflowRule.objects.filter(user=user, kind="EXPENSE", is_recurring=False).order_by("-next_due")

        for rule in list(recurring_qs) + list(one_time_qs):
            rule.next_due_display = rule.next_due_upcoming(base_today)

        latest_list = sorted(
            list(recurring_qs) + list(one_time_qs),
            key=lambda x: x.next_due_display or base_today,
            reverse=True,
        )

        total_recurring = month_total_recurring_rules(user, "EXPENSE", month_start, month_end)
        total_one_time = month_total_onetime_rules(user, "EXPENSE", month_start, month_end)
        total_incomes = (
            month_total_recurring_rules(user, "INCOME", month_start, month_end)
            + month_total_onetime_rules(user, "INCOME", month_start, month_end)
        )
        total_expenses = total_recurring + total_one_time
        net_cashflow = total_incomes - total_expenses

        cat_map, _ = month_rule_split(user, "EXPENSE", month_start, month_end)
        months = last_n_month_starts(12, ref=month_end)
        monthly_one_vals: list[float] = []
        monthly_rec_vals: list[float] = []
        for m in months:
            ms, me = month_bounds(m)
            monthly_one_vals.append(dec_to_float(month_total_onetime_rules(user, "EXPENSE", ms, me)))
            monthly_rec_vals.append(dec_to_float(month_total_recurring_rules(user, "EXPENSE", ms, me)))

        def with_ym(d: date) -> str:
            query = self.request.GET.copy()
            query["ym"] = ym_str(d)
            return f"{self.request.path}?{urlencode(query)}"

        ctx.update(
            latest_list=latest_list,
            recurring_list=recurring_qs,
            one_time_list=one_time_qs,
            month_start=month_start,
            month_end=month_end,
            cashflow_period_label=period_label,
            inout_period_label=period_label,
            total_recurring_month=total_recurring,
            total_one_time_month=total_one_time,
            total_incomes_month=total_incomes,
            total_expenses_month=total_expenses,
            net_cashflow_month=net_cashflow,
            donut_labels_json=json.dumps(list(cat_map.keys()), ensure_ascii=False),
            donut_data_json=json.dumps([dec_to_float(v) for v in cat_map.values()], ensure_ascii=False),
            months_labels_json=json.dumps([m.strftime("%b %Y") for m in months], ensure_ascii=False),
            monthly_rec_vals_json=json.dumps(monthly_rec_vals, ensure_ascii=False),
            monthly_one_vals_json=json.dumps(monthly_one_vals, ensure_ascii=False),
            ym_current=ym_str(month_start),
            url_prev_month=with_ym(prev_month_first),
            url_next_month=with_ym(next_month_first),
            holdings=Holding.objects.filter(user=user).select_related("account", "asset"),
        )
        return ctx


class AssetsView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/assets.html"
    login_url = reverse_lazy("fundboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["holdings"] = Holding.objects.filter(user=self.request.user).select_related("account", "asset")
        return ctx


class AccountsView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "fundboard/accounts.html"
    context_object_name = "accounts"
    login_url = reverse_lazy("fundboard:login")

    def get_queryset(self):
        qs = Account.objects.filter(user=self.request.user)
        balances = {
            row["account_id"]: (row["total"] or Decimal("0"))
            for row in (
                Leg.objects.filter(transaction__user=self.request.user)
                .values("account_id")
                .annotate(total=Sum("value_reference"))
            )
        }
        out = list(qs)
        for account in out:
            account.balance = balances.get(account.id, Decimal("0"))
        return out


class IncomesView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/incomes.html"
    login_url = reverse_lazy("fundboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        month_first = parse_ym(self.request, date.today())
        month_start, month_end = month_bounds(month_first)
        prev_month_first = (month_start - timedelta(days=1)).replace(day=1)
        next_month_first = (month_end + timedelta(days=1)).replace(day=1)
        period_label = month_start.strftime("%B %Y").capitalize()

        recurring_qs = CashflowRule.objects.filter(user=user, kind="INCOME", is_recurring=True).order_by("next_due")
        one_time_qs = CashflowRule.objects.filter(user=user, kind="INCOME", is_recurring=False).order_by("-next_due")
        for inc in list(recurring_qs) + list(one_time_qs):
            inc.next_payday_display = inc.next_due_upcoming(date.today())

        latest_list = sorted(
            list(recurring_qs) + list(one_time_qs),
            key=lambda x: x.next_payday_display or date.today(),
            reverse=True,
        )

        total_recurring = month_total_recurring_rules(user, "INCOME", month_start, month_end)
        total_onetime = month_total_onetime_rules(user, "INCOME", month_start, month_end)
        src_map, _ = month_rule_split(user, "INCOME", month_start, month_end)

        months = last_n_month_starts(12, ref=month_end)
        monthly_rec_vals = []
        monthly_one_vals = []
        for m in months:
            ms, me = month_bounds(m)
            monthly_rec_vals.append(dec_to_float(month_total_recurring_rules(user, "INCOME", ms, me)))
            monthly_one_vals.append(dec_to_float(month_total_onetime_rules(user, "INCOME", ms, me)))

        def with_ym(d: date) -> str:
            query = self.request.GET.copy()
            query["ym"] = ym_str(d)
            return f"{self.request.path}?{urlencode(query)}"

        ctx.update(
            recurring_list=recurring_qs,
            one_time_list=one_time_qs,
            latest_list=latest_list,
            ym_current=ym_str(month_start),
            url_prev_month=with_ym(prev_month_first),
            url_next_month=with_ym(next_month_first),
            income_period_label=period_label,
            total_recurring_income_month=total_recurring,
            total_onetime_income_month=total_onetime,
            total_income_month=total_recurring + total_onetime,
            incomes_donut_labels_json=json.dumps(list(src_map.keys()), ensure_ascii=False),
            incomes_donut_data_json=json.dumps([dec_to_float(v) for v in src_map.values()], ensure_ascii=False),
            months_labels_json=json.dumps([m.strftime("%b %Y") for m in months], ensure_ascii=False),
            monthly_rec_income_vals_json=json.dumps(monthly_rec_vals, ensure_ascii=False),
            monthly_one_income_vals_json=json.dumps(monthly_one_vals, ensure_ascii=False),
        )
        return ctx


class SubscriptionsRedirectView(RedirectView):
    pattern_name = "fundboard:expenses"


class AjaxModalMixin:
    template_name_fragment: str | None = None

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET" and request.headers.get("x-requested-with") != "XMLHttpRequest":
            return HttpResponseForbidden("Modal only.")
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        html = render_to_string(self.template_name_fragment, context, self.request)
        return HttpResponse(html)


class AccountSourceModal(LoginRequiredMixin, AjaxModalMixin, TemplateView):
    template_name_fragment = "fundboard/modals/account_source.html"


class AddAccountModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = "fundboard/modals/account_form.html"
    success_url = reverse_lazy("fundboard:accounts")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        messages.success(self.request, "Compte ajoute.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)


class EditAccountModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = "fundboard/modals/account_form.html"
    success_url = reverse_lazy("fundboard:accounts")

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Compte mis a jour.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)


class DeleteAccountModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    model = Account
    template_name_fragment = "fundboard/modals/account_delete.html"
    success_url = reverse_lazy("fundboard:accounts")

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Compte supprime.")
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            super().delete(request, *args, **kwargs)
            return HttpResponse(status=204)
        return super().delete(request, *args, **kwargs)


class AddExpenseModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    model = CashflowRule
    form_class = ExpenseForm
    template_name_fragment = "fundboard/modals/expense_form.html"
    success_url = reverse_lazy("fundboard:expenses")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        rec = self.request.GET.get("recurring")
        if rec in {"1", "true", "True"}:
            initial["is_recurring"] = True
        if rec in {"0", "false", "False"}:
            initial["is_recurring"] = False
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.kind = "EXPENSE"
        obj.save()
        messages.success(self.request, "Depense enregistree.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)


class EditExpenseModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = CashflowRule
    form_class = ExpenseForm
    template_name_fragment = "fundboard/modals/expense_form.html"
    success_url = reverse_lazy("fundboard:expenses")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        return CashflowRule.objects.filter(user=self.request.user, kind="EXPENSE")

    def form_valid(self, form):
        messages.success(self.request, "Depense mise a jour.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)


class DeleteExpenseModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    model = CashflowRule
    template_name_fragment = "fundboard/modals/expense_delete.html"
    success_url = reverse_lazy("fundboard:expenses")

    def get_queryset(self):
        return CashflowRule.objects.filter(user=self.request.user, kind="EXPENSE")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Depense supprimee.")
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            super().delete(request, *args, **kwargs)
            return HttpResponse(status=204)
        return super().delete(request, *args, **kwargs)


class AddIncomeModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    model = CashflowRule
    form_class = IncomeForm
    template_name_fragment = "fundboard/modals/income_form.html"
    success_url = reverse_lazy("fundboard:incomes")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        rec = self.request.GET.get("recurring")
        if rec in {"1", "true", "True"}:
            initial["is_recurring"] = True
        if rec in {"0", "false", "False"}:
            initial["is_recurring"] = False
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.kind = "INCOME"
        obj.save()
        messages.success(self.request, "Revenu enregistre.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)


class EditIncomeModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = CashflowRule
    form_class = IncomeForm
    template_name_fragment = "fundboard/modals/income_form.html"
    success_url = reverse_lazy("fundboard:incomes")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        return CashflowRule.objects.filter(user=self.request.user, kind="INCOME")

    def form_valid(self, form):
        messages.success(self.request, "Revenu mis a jour.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)


class DeleteIncomeModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    model = CashflowRule
    template_name_fragment = "fundboard/modals/income_delete.html"
    success_url = reverse_lazy("fundboard:incomes")

    def get_queryset(self):
        return CashflowRule.objects.filter(user=self.request.user, kind="INCOME")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Revenu supprime.")
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            super().delete(request, *args, **kwargs)
            return HttpResponse(status=204)
        return super().delete(request, *args, **kwargs)


class MarkIncomeModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    form_class = MarkIncomeForm
    template_name_fragment = "fundboard/modals/income_mark.html"
    success_url = reverse_lazy("fundboard:incomes")

    def get_object(self):
        return CashflowRule.objects.get(pk=self.kwargs["pk"], user=self.request.user, kind="INCOME")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["income_rule"] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        self.income = self.get_object()
        ctx["income"] = self.income
        return ctx

    def form_valid(self, form):
        income_rule = self.get_object()
        cleaned = form.cleaned_data
        account = cleaned["account"]
        fiat_asset, _ = Asset.objects.get_or_create(
            ticker=account.base_currency,
            defaults={
                "name": account.base_currency,
                "asset_type": "FIAT",
                "precision": 8,
            },
        )

        post_transaction(
            payload={
                "user": self.request.user,
                "trx_type": "DEPOSIT",
                "executed_at": cleaned["date_posted"],
                "description": cleaned.get("memo") or f"Income: {income_rule.name}",
            },
            legs=[
                LegInput(
                    account_id=account.id,
                    asset_id=fiat_asset.id,
                    quantity=cleaned["amount"],
                    value_reference=cleaned["amount"],
                    reference_currency=account.base_currency,
                )
            ],
        )

        if income_rule.is_recurring:
            income_rule.next_due = income_rule.next_due_upcoming(cleaned["date_posted"].date() + timedelta(days=1))
            income_rule.save(update_fields=["next_due", "updated_at"])

        messages.success(self.request, "Revenu marque comme recu.")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        return super().form_valid(form)

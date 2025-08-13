# FundBoard/views.py
from __future__ import annotations

import json
import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView, RedirectView
)

# --- Models & Forms ---
from .models import Account, Expense, Transaction
from .forms import ManualAccountForm, ExpenseForm


# ============================================================
#                         HELPERS
# ============================================================

def month_bounds(d: date) -> tuple[date, date]:
    """Return (first_day, last_day) for the month of date d."""
    first = d.replace(day=1)
    next_month_first = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = next_month_first - timedelta(days=1)
    return first, last


def last_n_month_starts(n: int, ref: date | None = None) -> list[date]:
    """Return a list of month-start dates for the last n months (ascending)."""
    if ref is None:
        ref = date.today()
    first_this, _ = month_bounds(ref)
    months: list[date] = []
    y, m = first_this.year, first_this.month
    for _i in range(n):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    return months


def dec_to_float(d: Decimal | None) -> float:
    """Safe conversion for JSON serialization."""
    return float(d or Decimal("0.0"))


def monthly_equivalent(exp: Expense) -> Decimal:
    """
    Compute monthly-equivalent amount for a recurring Expense.
    All math in Decimal to avoid float issues.
    """
    if not getattr(exp, "is_recurring", False):
        return Decimal("0")

    amt = exp.amount or Decimal("0")
    freq = exp.freq or ""
    DAYS_PER_MONTH = Decimal("30.4375")   # 365.25/12
    WEEKS_PER_MONTH = Decimal("4.345")    # ~52.14/12

    if freq == "MONTHLY":
        return amt
    if freq == "WEEKLY":
        return (amt * WEEKS_PER_MONTH).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if freq == "YEARLY":
        return (amt / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if freq == "DAILY":
        return (amt * DAYS_PER_MONTH).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if freq == "PERSONALIZED" and exp.freq_custom:
        days = Decimal(str(exp.freq_custom))
        if days > 0:
            factor = DAYS_PER_MONTH / days
            return (amt * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return amt


def _add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping the day when needed."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def upcoming_due(exp: Expense, ref: date | None = None) -> date:
    """
    Compute next upcoming due date for the expense given 'ref' (today by default).
    - For one-time: returns exp.next_due (or today if None).
    - For recurring: roll the date forward according to freq until >= ref.
    """
    if ref is None:
        ref = date.today()

    d = exp.next_due or ref
    if not exp.is_recurring:
        return d

    # roll forward by frequency
    if exp.freq == "DAILY":
        while d < ref:
            d = d + timedelta(days=1)
        return d

    if exp.freq == "WEEKLY":
        while d < ref:
            d = d + timedelta(weeks=1)
        return d

    if exp.freq == "MONTHLY":
        while d < ref:
            d = _add_months(d, 1)
        return d

    if exp.freq == "YEARLY":
        while d < ref:
            d = date(d.year + 1, d.month, min(d.day, calendar.monthrange(d.year + 1, d.month)[1]))
        return d

    if exp.freq == "PERSONALIZED" and exp.freq_custom:
        step = timedelta(days=exp.freq_custom)
        while d < ref:
            d = d + step
        return d

    return d


def month_expense_category_split(user, month_start: date, month_end: date) -> tuple[dict[str, Decimal], Decimal]:
    """
    Build a map category->Decimal for the current month combining:
      - recurring monthly-equivalent amounts
      - one-time expenses falling inside [month_start, month_end]
    Returns (category_map, total_sum).
    """
    cat_map: dict[str, Decimal] = {}

    # Recurring
    recurring_qs = Expense.objects.filter(user=user, is_recurring=True)
    for e in recurring_qs:
        tag = e.tag or "Autre"
        cat_map[tag] = cat_map.get(tag, Decimal("0")) + monthly_equivalent(e)

    # One-time
    one_time_qs = Expense.objects.filter(
        user=user, is_recurring=False, next_due__range=(month_start, month_end)
    )
    for e in one_time_qs:
        tag = e.tag or "Autre"
        cat_map[tag] = cat_map.get(tag, Decimal("0")) + (e.amount or Decimal("0"))

    total = sum(cat_map.values(), Decimal("0"))
    return cat_map, total


def month_total_deposits(user, month_start: date, month_end: date) -> Decimal:
    """
    Sum of cash inflows considered as 'Entrées' for cashflow.
    """
    return (
        Transaction.objects.filter(
            user=user, trx_type="DEPOSIT", date_trx__date__range=(month_start, month_end)
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0")
    )


# ============================================================
#                         PAGES
# ============================================================

class FundBoardView(LoginRequiredMixin, TemplateView):
    """Main dashboard: cards + charts including a simple cashflow (Sankey-like)."""
    template_name = 'fundboard/fundboard.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kwargs):
        user = self.request.user
        ctx = super().get_context_data(**kwargs)

        accounts_qs = Account.objects.filter(user=user)
        accounts_count = accounts_qs.count()
        inv_types = ['CTO', 'PEA', 'CRYPTO']
        investment_accounts_count = accounts_qs.filter(category__in=inv_types).count()
        total_balance = accounts_qs.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

        recent_transactions = Transaction.objects.filter(user=user).order_by('-date_trx')[:5]
        transactions_count = Transaction.objects.filter(user=user).count()
        subscriptions_count = Expense.objects.filter(user=user, is_recurring=True).count()

        month_start, month_end = month_bounds(date.today())
        period_label = month_start.strftime("%B %Y").capitalize()

        # Donut (outflows by category)
        cat_map, total_out = month_expense_category_split(user, month_start, month_end)
        donut_labels = list(cat_map.keys())
        donut_values = [dec_to_float(v) for v in cat_map.values()]

        # In/Out bar
        total_in = month_total_deposits(user, month_start, month_end)
        in_out_labels = ["Entrées", "Sorties"]
        in_out_values = [dec_to_float(total_in), dec_to_float(total_out)]

        # Simple cashflow links: Entrées -> Catégorie (amount)
        cf_links = [{"from": "Entrées", "to": tag, "flow": dec_to_float(amount)}
                    for tag, amount in cat_map.items() if amount > 0]

        ctx.update(
            accounts_count=accounts_count,
            investment_accounts_count=investment_accounts_count,
            transactions_count=transactions_count,
            subscriptions_count=subscriptions_count,
            recent_transactions=recent_transactions,
            total_balance=total_balance,

            donut_labels_json=json.dumps(donut_labels, ensure_ascii=False),
            donut_data_json=json.dumps(donut_values, ensure_ascii=False),
            in_out_labels_json=json.dumps(in_out_labels, ensure_ascii=False),
            in_out_values_json=json.dumps(in_out_values, ensure_ascii=False),
            cf_links_json=json.dumps(cf_links, ensure_ascii=False),
            cashflow_period_label=period_label,
            inout_period_label=period_label,
        )
        return ctx


class PortfolioView(LoginRequiredMixin, TemplateView):
    """Simple portfolio page (kept if you still want a dedicated route)."""
    template_name = 'fundboard/portfolio.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        inv_types = ['CTO', 'PEA', 'CRYPTO']
        ctx['investment_accounts'] = Account.objects.filter(user=user, category__in=inv_types)
        return ctx


class TransactionsView(LoginRequiredMixin, ListView):
    """Transaction history."""
    model = Transaction
    template_name = 'fundboard/transactions.html'
    context_object_name = 'transactions'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-date_trx')


class ExpensesView(LoginRequiredMixin, TemplateView):
    """
    Unified 'Expenses' page:
      - Tab 1 (default): Latest (chronological list of all expenses, with type & account)
      - Tab 2: Recurring
      - Tab 3: One-time
      - Tab 4: Assets (placeholder: uses 'holdings' if/when provided)
      - Charts: donut by category (current month), stacked bar (6 months)
    """
    template_name = 'fundboard/expenses.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Querysets
        recurring_qs = Expense.objects.filter(user=user, is_recurring=True).order_by('next_due')
        one_time_qs  = Expense.objects.filter(user=user, is_recurring=False).order_by('-next_due')

        # Compute display 'upcoming' dates (server-side) to avoid relying on template logic
        today = date.today()
        for e in list(recurring_qs) + list(one_time_qs):
            e.next_due_display = upcoming_due(e, today)

        # Latest (merged list), ordered desc by upcoming/display date
        latest_list = sorted(
            list(recurring_qs) + list(one_time_qs),
            key=lambda x: x.next_due_display or today,
            reverse=True
        )

        # Current month aggregates for charts
        month_start, month_end = month_bounds(today)
        total_recurring = sum((monthly_equivalent(e) for e in recurring_qs), Decimal("0.00"))
        total_one_time = one_time_qs.filter(next_due__range=(month_start, month_end)) \
                                    .aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

        # Donut split
        cat_map, _ = month_expense_category_split(user, month_start, month_end)
        donut_labels = list(cat_map.keys())
        donut_data = [dec_to_float(v) for v in cat_map.values()]

        # 6-month stacked bars
        months = last_n_month_starts(6)
        months_labels = [m.strftime("%b %Y") for m in months]
        monthly_one_vals: list[float] = []
        for m in months:
            ms, me = month_bounds(m)
            one_m = one_time_qs.filter(next_due__range=(ms, me)).aggregate(s=Sum('amount'))['s'] or Decimal("0")
            monthly_one_vals.append(dec_to_float(one_m))
        monthly_rec_vals = [dec_to_float(total_recurring) for _ in months]

        # Assets tab placeholder (so template doesn't error if not provided)
        ctx.update(
            latest_list=latest_list,
            recurring_list=recurring_qs,
            one_time_list=one_time_qs,
            total_recurring_month=total_recurring,
            total_one_time_month=total_one_time,
            month_start=month_start,
            month_end=month_end,

            donut_labels_json=json.dumps(donut_labels, ensure_ascii=False),
            donut_data_json=json.dumps(donut_data, ensure_ascii=False),
            months_labels_json=json.dumps(months_labels, ensure_ascii=False),
            monthly_rec_vals_json=json.dumps(monthly_rec_vals, ensure_ascii=False),
            monthly_one_vals_json=json.dumps(monthly_one_vals, ensure_ascii=False),

            holdings=[]  # replace with real holdings later
        )
        return ctx


class AssetsView(LoginRequiredMixin, TemplateView):
    """Deprecated in favor of the Expenses 'Actifs' tab. Kept if you still browse /assets/."""
    template_name = 'fundboard/assets.html'
    login_url = reverse_lazy('fundboard:login')


class AccountsView(LoginRequiredMixin, ListView):
    """Accounts list page."""
    model = Account
    template_name = 'fundboard/accounts.html'
    context_object_name = 'accounts'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)


class RevenuesView(LoginRequiredMixin, TemplateView):
    """Placeholder Revenues page."""
    template_name = 'fundboard/revenues.html'
    login_url = reverse_lazy('fundboard:login')


class SubscriptionsRedirectView(RedirectView):
    """Backward-compat route: /subscriptions -> /expenses"""
    pattern_name = 'fundboard:expenses'


# ============================================================
#                   AJAX MODALS (shared mixin)
# ============================================================

class AjaxModalMixin:
    """Render fragments for GET; forbid non-AJAX GET; return HTML body."""
    template_name_fragment: str | None = None

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET" and request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return HttpResponseForbidden("Modal only.")
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        html = render_to_string(self.template_name_fragment, context, self.request)
        return HttpResponse(html)


# ============================================================
#                   ACCOUNT MODALS (AJAX)
# ============================================================

class AccountSourceModal(LoginRequiredMixin, AjaxModalMixin, TemplateView):
    """First step modal (choose connector)."""
    template_name_fragment = "fundboard/modals/account_source.html"


class AddAccountModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    """Manual account creation modal."""
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url = reverse_lazy('fundboard:accounts')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        messages.success(self.request, "Compte ajouté.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)


class EditAccountModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url = reverse_lazy('fundboard:accounts')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Compte mis à jour.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)


class DeleteAccountModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    model = Account
    template_name_fragment = 'fundboard/modals/account_delete.html'
    success_url = reverse_lazy('fundboard:accounts')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Compte supprimé.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            super().delete(request, *args, **kwargs)
            return HttpResponse(status=204)
        return super().delete(request, *args, **kwargs)


# ============================================================
#                   EXPENSE MODALS (AJAX)
# ============================================================

class AddExpenseModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name_fragment = 'fundboard/modals/expense_form.html'
    success_url = reverse_lazy('fundboard:expenses')

    def get_initial(self):
        initial = super().get_initial()
        rec = self.request.GET.get('recurring')
        if rec in {'1', 'true', 'True'}:
            initial['is_recurring'] = True
        if rec in {'0', 'false', 'False'}:
            initial['is_recurring'] = False
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        messages.success(self.request, "Dépense enregistrée.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)


class EditExpenseModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name_fragment = 'fundboard/modals/expense_form.html'
    success_url = reverse_lazy('fundboard:expenses')

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Dépense mise à jour.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)


class DeleteExpenseModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    model = Expense
    template_name_fragment = 'fundboard/modals/expense_delete.html'
    success_url = reverse_lazy('fundboard:expenses')

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Dépense supprimée.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            super().delete(request, *args, **kwargs)
            return HttpResponse(status=204)
        return super().delete(request, *args, **kwargs)

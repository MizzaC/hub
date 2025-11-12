# FundBoard/views.py
from __future__ import annotations

import json
import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from django.utils.http import urlencode
from django.db.models import Q

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
from .models import Account, Expense, Transaction, Income
from .forms import (
    ManualAccountForm,
    ExpenseForm,
    IncomeForm,
    MarkIncomeForm,
)

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
    """Compute monthly-equivalent amount for a recurring Expense."""
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


def upcoming_due(obj, ref: date | None = None) -> date:
    """
    Compute next upcoming due date for Expense/Income given 'ref' (today by default).
    - For one-time: returns obj.next_due/next_payday (or today if None).
    - For recurring: roll the date forward according to freq until >= ref.
    """
    if ref is None:
        ref = date.today()

    # support both Expense (next_due) and Income (next_payday)
    base_date = getattr(obj, "next_due", None) or getattr(obj, "next_payday", None) or ref
    d = base_date
    is_rec = getattr(obj, "is_recurring", False)
    freq = getattr(obj, "freq", None)
    freq_custom = getattr(obj, "freq_custom", None)

    if not is_rec:
        return d

    if freq == "DAILY":
        while d < ref:
            d = d + timedelta(days=1)
        return d

    if freq == "WEEKLY":
        while d < ref:
            d = d + timedelta(weeks=1)
        return d

    if freq == "MONTHLY":
        while d < ref:
            d = _add_months(d, 1)
        return d

    if freq == "YEARLY":
        while d < ref:
            d = date(d.year + 1, d.month, min(d.day, calendar.monthrange(d.year + 1, d.month)[1]))
        return d

    if freq == "PERSONALIZED" and freq_custom:
        step = timedelta(days=freq_custom)
        while d < ref:
            d = d + step
        return d

    return d


def month_expense_category_split(user, month_start: date, month_end: date) -> tuple[dict[str, Decimal], Decimal]:
    """
    Catégorie -> somme pour le mois sélectionné, en respectant start_date/end_date :
    - Récurrentes : ajoutent leur monthly_equivalent() uniquement si actives dans le mois.
    - Ponctuelles : prises si next_due ∈ [month_start, month_end].
    """
    cat_map: dict[str, Decimal] = {}

    # Récurrentes actives sur le mois
    recurring_qs = Expense.objects.filter(user=user, is_recurring=True).filter(
        Q(start_date__lte=month_end) & (Q(end_date__isnull=True) | Q(end_date__gte=month_start))
    )

    for e in recurring_qs:
        tag = e.tag or "Autre"
        cat_map[tag] = cat_map.get(tag, Decimal("0")) + e.monthly_equivalent()

    # Ponctuelles dans la fenêtre
    one_time_qs = Expense.objects.filter(
        user=user, is_recurring=False, next_due__range=(month_start, month_end)
    )

    for e in one_time_qs:
        tag = e.tag or "Autre"
        cat_map[tag] = cat_map.get(tag, Decimal("0")) + (e.amount or Decimal("0"))

    total = sum(cat_map.values(), Decimal("0"))
    return cat_map, total


def month_income_source_split(user, month_start: date, month_end: date) -> tuple[dict[str, Decimal], Decimal]:
    """
    Source (ou tag/nom) -> somme des revenus du mois, en respectant start_date/end_date :
    - Récurrents actifs : monthly_equivalent()
    - Ponctuels : si next_payday ∈ [month_start, month_end]
    """
    src_map: dict[str, Decimal] = {}

    recurring_qs = Income.objects.filter(user=user, is_recurring=True).filter(
        Q(start_date__lte=month_end) & (Q(end_date__isnull=True) | Q(end_date__gte=month_start))
    )
    for i in recurring_qs:
        label = getattr(i, "source", None) or getattr(i, "tag", None) or i.name or "Autre"
        src_map[label] = src_map.get(label, Decimal("0")) + i.monthly_equivalent()

    one_time_qs = Income.objects.filter(
        user=user, is_recurring=False, next_payday__range=(month_start, month_end)
    )
    for i in one_time_qs:
        label = getattr(i, "source", None) or getattr(i, "tag", None) or i.name or "Autre"
        src_map[label] = src_map.get(label, Decimal("0")) + (i.amount or Decimal("0"))

    total = sum(src_map.values(), Decimal("0"))
    return src_map, total


def month_total_deposits(user, month_start: date, month_end: date) -> Decimal:
    """Sum of 'DEPOSIT' transactions in period."""
    return (
        Transaction.objects.filter(
            user=user, trx_type="DEPOSIT", date_trx__date__range=(month_start, month_end)
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0")
    )

def parse_ym(request, fallback_date: date) -> date:
    """
    Lit 'ym' au format YYYY-MM dans la querystring et renvoie un date() sur le 1er du mois.
    Sinon renvoie fallback_date normalisé au 1er du mois.
    """
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

def month_is_active_for(obj, month_start: date, month_end: date) -> bool:
    """
    Vrai si l'objet (Expense/Income) est actif durant la fenêtre [month_start, month_end].
    Règle : start_date <= month_end AND (end_date is null OR end_date >= month_start)
    """
    sd = getattr(obj, "start_date", None)
    ed = getattr(obj, "end_date", None)
    if sd and sd > month_end:
        return False
    if ed and ed < month_start:
        return False
    return True

def month_total_recurring_expenses_active(user, month_start: date, month_end: date) -> Decimal:
    qs = Expense.objects.filter(user=user, is_recurring=True).filter(
        Q(start_date__lte=month_end) & (Q(end_date__isnull=True) | Q(end_date__gte=month_start))
    )
    return sum((e.monthly_equivalent() for e in qs), Decimal("0.00"))

def month_total_onetime_expenses(user, month_start: date, month_end: date) -> Decimal:
    return Expense.objects.filter(
        user=user, is_recurring=False, next_due__range=(month_start, month_end)
    ).aggregate(s=Sum('amount'))['s'] or Decimal("0.00")

def month_total_recurring_incomes_active(user, month_start: date, month_end: date) -> Decimal:
    qs = Income.objects.filter(user=user, is_recurring=True).filter(
        Q(start_date__lte=month_end) & (Q(end_date__isnull=True) | Q(end_date__gte=month_start))
    )
    return sum((i.monthly_equivalent() for i in qs), Decimal("0.00"))

def month_total_onetime_incomes(user, month_start: date, month_end: date) -> Decimal:
    return Income.objects.filter(
        user=user, is_recurring=False, next_payday__range=(month_start, month_end)
    ).aggregate(s=Sum('amount'))['s'] or Decimal("0.00")

def month_total_incomes_active(user, month_start: date, month_end: date) -> Decimal:
    """
    Revenus du mois : récurrents actifs (monthly_equivalent) + ponctuels (next_payday in window).
    """
    rec = month_total_recurring_incomes_active(user, month_start, month_end)
    one = month_total_onetime_incomes(user, month_start, month_end)
    return rec + one

# ============================================================
#                         PAGES
# ============================================================

class FundBoardView(LoginRequiredMixin, TemplateView):
    """Main dashboard."""
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
            active_period_label=f"{month_start:%d/%m/%Y} → {month_end:%d/%m/%Y}",

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
    template_name = 'fundboard/portfolio.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        inv_types = ['CTO', 'PEA', 'CRYPTO']
        ctx['investment_accounts'] = Account.objects.filter(user=user, category__in=inv_types)
        return ctx


class TransactionsView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'fundboard/transactions.html'
    context_object_name = 'transactions'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-date_trx')


class ExpensesView(LoginRequiredMixin, TemplateView):
    """Unified Expenses page (Latest + Recurring + One-time + charts)."""
    template_name = 'fundboard/expenses.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # --- Mois sélectionné (via ?ym=YYYY-MM), navigation ---
        base_today = date.today()
        month_first = parse_ym(self.request, base_today)  # 1er du mois choisi
        month_start, month_end = month_bounds(month_first)
        prev_month_first = (month_start - timedelta(days=1)).replace(day=1)
        next_month_first = (month_end + timedelta(days=1)).replace(day=1)
        period_label = month_start.strftime("%B %Y").capitalize()

        # --- Listes Latest / Recurring / One-time (avec next_due_display calculé) ---
        recurring_qs = Expense.objects.filter(user=user, is_recurring=True).order_by('next_due')
        one_time_qs  = Expense.objects.filter(user=user, is_recurring=False).order_by('-next_due')

        today = base_today
        for e in list(recurring_qs) + list(one_time_qs):
            e.next_due_display = upcoming_due(e, today)

        latest_list = sorted(
            list(recurring_qs) + list(one_time_qs),
            key=lambda x: x.next_due_display or today,
            reverse=True
        )

        # --- KPI du mois sélectionné (respecte start/end) ---
        total_recurring = month_total_recurring_expenses_active(user, month_start, month_end)
        total_one_time  = month_total_onetime_expenses(user, month_start, month_end)
        total_incomes   = month_total_incomes_active(user, month_start, month_end)
        total_expenses  = total_recurring + total_one_time
        net_cashflow    = (total_incomes or Decimal('0')) - (total_expenses or Decimal('0'))

        # --- Donut catégorie (mois sélectionné) ---
        cat_map, _ = month_expense_category_split(user, month_start, month_end)
        donut_labels = list(cat_map.keys())
        donut_data   = [dec_to_float(v) for v in cat_map.values()]

        # --- Série 12 mois: du mois sélectionné - 11 mois, vers le mois sélectionné ---
        months = last_n_month_starts(12, ref=month_end)
        months_labels = [m.strftime("%b %Y") for m in months]
        monthly_one_vals: list[float] = []
        monthly_rec_vals: list[float] = []
        for m in months:
            ms, me = month_bounds(m)
            one_m = month_total_onetime_expenses(user, ms, me)
            rec_m = month_total_recurring_expenses_active(user, ms, me)
            monthly_one_vals.append(dec_to_float(one_m))
            monthly_rec_vals.append(dec_to_float(rec_m))

        # --- URLs navigation ---
        def with_ym(d: date) -> str:
            base = self.request.path
            query = self.request.GET.copy()
            query['ym'] = ym_str(d)
            return f"{base}?{urlencode(query)}"

        ctx.update(
            # tables
            latest_list=latest_list,
            recurring_list=recurring_qs,
            one_time_list=one_time_qs,

            # période
            month_start=month_start,
            month_end=month_end,
            cashflow_period_label=period_label,
            inout_period_label=period_label,

            # cards
            total_recurring_month=total_recurring,
            total_one_time_month=total_one_time,
            total_incomes_month=total_incomes,
            total_expenses_month=total_expenses,
            net_cashflow_month=net_cashflow,

            # donut mois sélectionné
            donut_labels_json=json.dumps(donut_labels, ensure_ascii=False),
            donut_data_json=json.dumps(donut_data, ensure_ascii=False),

            # bar 12 mois empilé
            months_labels_json=json.dumps(months_labels, ensure_ascii=False),
            monthly_rec_vals_json=json.dumps(monthly_rec_vals, ensure_ascii=False),
            monthly_one_vals_json=json.dumps(monthly_one_vals, ensure_ascii=False),

            # nav mois
            ym_current=ym_str(month_start),
            ym_prev=ym_str(prev_month_first),
            ym_next=ym_str(next_month_first),
            url_prev_month=with_ym(prev_month_first),
            url_next_month=with_ym(next_month_first),

            # holdings (inchangé)
            holdings=[],
        )
        return ctx


class AssetsView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/assets.html'
    login_url = reverse_lazy('fundboard:login')


class AccountsView(LoginRequiredMixin, ListView):
    model = Account
    template_name = 'fundboard/accounts.html'
    context_object_name = 'accounts'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)


class IncomesView(LoginRequiredMixin, TemplateView):
    """Incomes page (latest + recurring + one-time + charts, avec navigation mensuelle)."""
    template_name = 'fundboard/incomes.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # --- Mois sélectionné & navigation ---
        base_today = date.today()
        month_first = parse_ym(self.request, base_today)
        month_start, month_end = month_bounds(month_first)
        prev_month_first = (month_start - timedelta(days=1)).replace(day=1)
        next_month_first = (month_end + timedelta(days=1)).replace(day=1)
        period_label = month_start.strftime("%B %Y").capitalize()

        # --- Listes (ordre + next_payday_display) ---
        recurring_qs = Income.objects.filter(user=user, is_recurring=True).order_by('next_payday')
        one_time_qs  = Income.objects.filter(user=user, is_recurring=False).order_by('-next_payday')

        today = base_today
        for inc in list(recurring_qs) + list(one_time_qs):
            inc.next_payday_display = upcoming_due(inc, today)

        latest_list = sorted(
            list(recurring_qs) + list(one_time_qs),
            key=lambda x: x.next_payday_display or today,
            reverse=True
        )

        # --- KPI revenus du mois ---
        total_recurring_income_month = month_total_recurring_incomes_active(user, month_start, month_end)
        total_onetime_income_month   = month_total_onetime_incomes(user, month_start, month_end)
        total_income_month           = total_recurring_income_month + total_onetime_income_month

        # --- Donut par source (mois) ---
        src_map, _ = month_income_source_split(user, month_start, month_end)
        incomes_donut_labels = list(src_map.keys())
        incomes_donut_data   = [dec_to_float(v) for v in src_map.values()]

        # --- Série 12 mois revenus ---
        months = last_n_month_starts(12, ref=month_end)
        months_labels = [m.strftime("%b %Y") for m in months]
        monthly_rec_income_vals: list[float] = []
        monthly_one_income_vals: list[float] = []
        for m in months:
            ms, me = month_bounds(m)
            monthly_rec_income_vals.append(dec_to_float(month_total_recurring_incomes_active(user, ms, me)))
            monthly_one_income_vals.append(dec_to_float(month_total_onetime_incomes(user, ms, me)))

        # --- URLs navigation ---
        def with_ym(d: date) -> str:
            base = self.request.path
            query = self.request.GET.copy()
            query['ym'] = ym_str(d)
            return f"{base}?{urlencode(query)}"

        ctx.update(
            # tables
            recurring_list=recurring_qs,
            one_time_list=one_time_qs,
            latest_list=latest_list,

            # période
            ym_current=ym_str(month_start),
            url_prev_month=with_ym(prev_month_first),
            url_next_month=with_ym(next_month_first),
            income_period_label=period_label,

            # cards
            total_recurring_income_month=total_recurring_income_month,
            total_onetime_income_month=total_onetime_income_month,
            total_income_month=total_income_month,

            # charts
            incomes_donut_labels_json=json.dumps(incomes_donut_labels, ensure_ascii=False),
            incomes_donut_data_json=json.dumps(incomes_donut_data, ensure_ascii=False),
            months_labels_json=json.dumps(months_labels, ensure_ascii=False),
            monthly_rec_income_vals_json=json.dumps(monthly_rec_income_vals, ensure_ascii=False),
            monthly_one_income_vals_json=json.dumps(monthly_one_income_vals, ensure_ascii=False),
        )
        return ctx


class SubscriptionsRedirectView(RedirectView):
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
    template_name_fragment = "fundboard/modals/account_source.html"


class AddAccountModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
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
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs


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
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


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

# ============================================================
#                    INCOME MODALS (AJAX)
# ============================================================

class AddIncomeModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    """Create income (modal)."""
    model = Income
    form_class = IncomeForm
    template_name_fragment = 'fundboard/modals/income_form.html'
    success_url = reverse_lazy('fundboard:incomes')

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
        messages.success(self.request, "Revenu enregistré.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)


class EditIncomeModal(LoginRequiredMixin, AjaxModalMixin, UpdateView):
    """Edit income (modal)."""
    model = Income
    form_class = IncomeForm
    template_name_fragment = 'fundboard/modals/income_form.html'
    success_url = reverse_lazy('fundboard:incomes')

    def get_queryset(self):
        return Income.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Revenu mis à jour.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)


class DeleteIncomeModal(LoginRequiredMixin, AjaxModalMixin, DeleteView):
    """Delete income (modal)."""
    model = Income
    template_name_fragment = 'fundboard/modals/income_delete.html'
    success_url = reverse_lazy('fundboard:incomes')

    def get_queryset(self):
        return Income.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Revenu supprimé.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            super().delete(request, *args, **kwargs)
            return HttpResponse(status=204)
        return super().delete(request, *args, **kwargs)


class MarkIncomeModal(LoginRequiredMixin, AjaxModalMixin, CreateView):
    """
    Mark an income as received: this typically creates a DEPOSIT transaction
    and optionally updates next_payday (for recurring incomes).
    """
    form_class = MarkIncomeForm
    template_name_fragment = 'fundboard/modals/income_mark.html'
    success_url = reverse_lazy('fundboard:incomes')

    # we use get_object to fetch the income being marked
    def get_object(self):
        return Income.objects.get(pk=self.kwargs["pk"], user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        income = self.get_object()
        # expose income on the view for template access via {{ view.income }}
        self.income = income
        ctx["income"] = income
        return ctx

    def form_valid(self, form):
        income = self.get_object()
        cleaned = form.cleaned_data

        # create a deposit transaction
        Transaction.objects.create(
            user=self.request.user,
            account=cleaned["account"],
            amount=cleaned["amount"],
            date_trx=cleaned["date_posted"],
            trx_type="DEPOSIT",
            memo=cleaned.get("memo") or f"Income: {income.name}",
        )

        # update next payday if recurring
        if income.is_recurring:
            income.next_payday = upcoming_due(income, ref=cleaned["date_posted"] + timedelta(days=1))
            income.save(update_fields=["next_payday"])

        messages.success(self.request, "Revenu marqué comme reçu.")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=204)
        return super().form_valid(form)

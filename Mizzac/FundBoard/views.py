# FundBoard/views.py
"""
Views for FundBoard.
- Unified "Expenses" page (recurring + one-time)
- Single modal form for both types (ExpenseForm + is_recurring toggle)
- Legacy /subscriptions redirects to /expenses
- FIX: chart datasets are now JSON-serialized in the context
"""

from datetime import date
from calendar import monthrange
import json

from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView
)
from django.views.generic.base import RedirectView
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.utils import timezone
from django.contrib import messages

from .models import (
    Account,
    Transaction, TRANSACTION_TYPES,
    Expense, Income
)
from .forms import (
    ManualAccountForm,
    ExpenseForm,
    IncomeForm
)


# ======================================================================
#                             DASHBOARD & PAGES
# ======================================================================

class FundBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/fundboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        accounts_qs     = Account.objects.filter(user=user)
        transactions_qs = Transaction.objects.filter(user=user)
        recurring_qs    = Expense.objects.filter(user=user, is_recurring=True)

        ctx['accounts_count'] = accounts_qs.count()
        ctx['investment_accounts_count'] = accounts_qs.filter(
            category__in=['CTO', 'PEA', 'CRYPTO']
        ).count()
        ctx['transactions_count'] = transactions_qs.count()
        ctx['subscriptions_count'] = recurring_qs.count()
        ctx['recent_transactions'] = transactions_qs.select_related('account', 'asset').order_by('-date_trx')[:5]
        ctx['total_balance'] = accounts_qs.aggregate(Sum('balance'))['balance__sum'] or 0

        return ctx


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/portfolio.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['investment_accounts'] = Account.objects.filter(
            user=user, category__in=['CTO', 'PEA', 'CRYPTO']
        ).order_by('name')
        return ctx


class TransactionsView(LoginRequiredMixin, ListView):
    """Transactions list with preloaded FKs; template provides client-side filters."""
    model = Transaction
    template_name = 'fundboard/transactions.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return (
            Transaction.objects
            .filter(user=self.request.user)
            .select_related('account', 'asset')
            .order_by('-date_trx')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['accounts'] = Account.objects.filter(user=self.request.user).order_by('name')
        ctx['transaction_choices'] = TRANSACTION_TYPES
        return ctx


# -------------------- Unified EXPENSES page (recurring + one-time) --------------------

class ExpensesView(LoginRequiredMixin, TemplateView):
    """
    Unified expenses page with two tabs:
      - Recurring (Expense.is_recurring=True)
      - One-time  (Expense.is_recurring=False)
    Provides simple aggregates and datasets for charts.
    """
    template_name = 'fundboard/expenses.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        recurring_qs = Expense.objects.filter(user=user, is_recurring=True).order_by('next_due')
        onetime_qs   = Expense.objects.filter(user=user, is_recurring=False).order_by('-next_due')

        # ---- Totals for headline cards ----
        def monthly_eq(exp):
            if exp.is_recurring:
                if exp.freq == 'MONTHLY':
                    return exp.amount
                if exp.freq == 'WEEKLY':
                    return exp.amount * 4.33
                if exp.freq == 'DAILY':
                    return exp.amount * 30
                if exp.freq == 'YEARLY':
                    return exp.amount / 12
                if exp.freq == 'PERSONALIZED' and exp.freq_custom:
                    return exp.amount * (30 / exp.freq_custom)
            return 0

        recurring_month_total = sum(monthly_eq(e) for e in recurring_qs)
        recurring_year_total  = recurring_month_total * 12

        # One-time totals limited to current month / year
        month_start = today.replace(day=1)
        year_start  = today.replace(month=1, day=1)
        onetime_month_total = sum(
            e.amount for e in onetime_qs if month_start <= e.next_due <= today
        )
        onetime_year_total = sum(
            e.amount for e in onetime_qs if year_start <= e.next_due <= today
        )

        # Donut by type (Recurring vs One-time)
        donut_labels = ['Recurring', 'One-time']
        donut_data   = [
            float(sum(e.amount for e in recurring_qs) or 0),
            float(sum(e.amount for e in onetime_qs) or 0)
        ]

        # Last 6 months stacked bars
        months = []
        y, m = today.year, today.month
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        months.reverse()
        months_labels = [f"{m:02d}/{y}" for (y, m) in months]

        monthly_rec_vals = [float(recurring_month_total) for _ in months]
        monthly_one_vals = []
        for y, m in months:
            start = date(y, m, 1)
            end   = date(y, m, monthrange(y, m)[1])
            total = sum(e.amount for e in onetime_qs if start <= e.next_due <= end)
            monthly_one_vals.append(float(total or 0))

        # Normal context variables (querysets etc.)
        ctx.update(
            recurring=recurring_qs,
            onetime=onetime_qs,
            recurring_month_total=recurring_month_total,
            recurring_year_total=recurring_year_total,
            onetime_month_total=onetime_month_total,
            onetime_year_total=onetime_year_total,
        )

        # 🚀 FIX: JSON-serialize datasets for Chart.js
        ctx.update(
            donut_labels_json=json.dumps(donut_labels),
            donut_data_json=json.dumps(donut_data),
            months_labels_json=json.dumps(months_labels),
            monthly_rec_vals_json=json.dumps(monthly_rec_vals),
            monthly_one_vals_json=json.dumps(monthly_one_vals),
        )
        return ctx


# ======================================================================
#                           AJAX MODAL MIXIN
# ======================================================================

class AjaxModalMixin:
    """
    Minimal mixin to ensure:
      - GET is AJAX-only (prevents direct navigation)
      - Render a partial fragment as raw HTML
    """
    template_name_fragment = None

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET" and request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return HttpResponseForbidden("Modal only.")
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        html = render_to_string(self.template_name_fragment, context, self.request)
        return HttpResponse(html)


# ======================================================================
#                              ACCOUNT MODALS
# ======================================================================

class AccountSourceModal(AjaxModalMixin, TemplateView):
    template_name_fragment = "fundboard/modals/account_source.html"


class AddAccountModal(AjaxModalMixin, CreateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url = reverse_lazy('fundboard:accounts')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Account added.")
        return super().form_valid(form)


class EditAccountModal(AjaxModalMixin, UpdateView):
    model = Account
    form_class = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url = reverse_lazy('fundboard:accounts')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Account updated.")
        return super().form_valid(form)


class DeleteAccountModal(AjaxModalMixin, DeleteView):
    model = Account
    template_name_fragment = 'fundboard/modals/account_delete.html'
    success_url = reverse_lazy('fundboard:accounts')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Account deleted.")
        return super().delete(request, *args, **kwargs)


# ======================================================================
#                           EXPENSE MODALS (unified)
# ======================================================================

class AddExpenseModal(AjaxModalMixin, CreateView):
    """Unified modal to add recurring OR one-time Expense (controlled by is_recurring)."""
    model = Expense
    form_class = ExpenseForm
    template_name_fragment = 'fundboard/modals/expense_form.html'
    success_url = reverse_lazy('fundboard:expenses')

    def get_initial(self):
        init = super().get_initial()
        rec = self.request.GET.get('recurring')
        if rec is not None:
            try:
                init['is_recurring'] = bool(int(rec))
            except ValueError:
                pass
        return init

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Expense added.")
        return super().form_valid(form)


class EditExpenseModal(AjaxModalMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name_fragment = 'fundboard/modals/expense_form.html'
    success_url = reverse_lazy('fundboard:expenses')

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Expense updated.")
        return super().form_valid(form)


class DeleteExpenseModal(AjaxModalMixin, DeleteView):
    model = Expense
    template_name_fragment = 'fundboard/modals/expense_delete.html'
    success_url = reverse_lazy('fundboard:expenses')

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Expense deleted.")
        return super().delete(request, *args, **kwargs)


# ======================================================================
#                                  OTHERS
# ======================================================================

class AccountsView(LoginRequiredMixin, ListView):
    model = Account
    template_name = 'fundboard/accounts.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user).order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['manual_form'] = ManualAccountForm()
        return ctx


class RevenuesView(LoginRequiredMixin, ListView):
    model = Income
    template_name = 'fundboard/revenues.html'
    context_object_name = 'revenues'

    def get_queryset(self):
        return Income.objects.filter(user=self.request.user).order_by('next_payday')


# ---------------- Redirect legacy /subscriptions → /expenses ----------------

class SubscriptionsRedirectView(RedirectView):
    pattern_name = 'fundboard:expenses'
    permanent = True

from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView
)
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.contrib import messages

from .models import (
    Account, Transaction, TRANSACTION_TYPES,
    Subscription, Income
)
from .forms import SubscriptionForm, ManualAccountForm   # renomme AbonnementForm -> SubscriptionForm

# ════════════════════════════════════════════════════════════════
# 1.  Dashboard & pages classiques
# ════════════════════════════════════════════════════════════════
class FundBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/fundboard.html'
    login_url     = reverse_lazy('fundboard:login')

    def get_context_data(self, **kw):
        user = self.request.user
        ctx  = super().get_context_data(**kw)

        ctx['accounts_count']            = Account.objects.filter(
            user=user, category__in=['CURRENT', 'SAVINGS']).count()
        ctx['investment_accounts_count'] = Account.objects.filter(
            user=user, category__in=['CTO', 'PEA', 'CRYPTO']).count()
        ctx['transactions_count']  = Transaction.objects.filter(user=user).count()
        ctx['subscriptions_count'] = Subscription.objects.filter(user=user).count()
        ctx['recent_transactions'] = Transaction.objects.filter(user=user)\
                                                         .order_by('-date_trx')[:5]
        ctx['total_balance'] = Account.objects.filter(user=user)\
                               .aggregate(total=Sum('balance'))['total'] or 0
        return ctx


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/portfolio.html'
    login_url     = reverse_lazy('fundboard:login')

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx['investment_accounts'] = Account.objects.filter(
            user=self.request.user, category__in=['CTO', 'PEA', 'CRYPTO'])
        return ctx


class TransactionsView(LoginRequiredMixin, ListView):
    model               = Transaction
    template_name       = 'fundboard/transactions.html'
    context_object_name = 'transactions'
    login_url           = reverse_lazy('fundboard:login')

    # liste filtrée : toutes les transactions de l’utilisateur, récentes d’abord
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user) \
                                  .select_related('account', 'asset') \
                                  .order_by('-date_trx')

    # données supplémentaires pour les filtres du template
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['accounts']            = Account.objects.filter(user=self.request.user)
        ctx['transaction_choices'] = TRANSACTION_TYPES      # pour <option> Type
        return ctx


# ════════════════════════════════════════════════════════════════
# 2.  Abonnements (pages complètes)
# ════════════════════════════════════════════════════════════════
class SubscriptionsView(LoginRequiredMixin, ListView):
    model               = Subscription
    template_name       = 'fundboard/subscriptions.html'
    context_object_name = 'subscriptions'
    login_url           = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)\
                                   .order_by('next_due')

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        qs  = Subscription.objects.filter(user=self.request.user)\
                                  .values('freq').annotate(total=Sum('amount'))
        ctx['labels'] = [r['freq'].title() for r in qs]
        ctx['data']   = [r['total'] for r in qs]
        return ctx


class AddSubscriptionView(LoginRequiredMixin, CreateView):
    model         = Subscription
    form_class    = SubscriptionForm
    template_name = 'fundboard/subscriptions_form.html'
    success_url   = reverse_lazy('fundboard:subscriptions')
    login_url     = reverse_lazy('fundboard:login')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Abonnement ajouté.")
        return super().form_valid(form)


class EditSubscriptionView(AddSubscriptionView, UpdateView):
    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Abonnement mis à jour.")
        return super().form_valid(form)


class DeleteSubscriptionView(LoginRequiredMixin, DeleteView):
    model         = Subscription
    template_name = 'fundboard/subscriptions_delete.html'
    success_url   = reverse_lazy('fundboard:subscriptions')
    login_url     = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def delete(self, request, *a, **kw):
        messages.success(request, "Abonnement supprimé.")
        return super().delete(request, *a, **kw)


# ════════════════════════════════════════════════════════════════
# 3.  Revenus
# ════════════════════════════════════════════════════════════════
class RevenuesView(LoginRequiredMixin, ListView):
    model               = Income
    template_name       = 'fundboard/revenues.html'
    context_object_name = 'revenues'
    login_url           = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Income.objects.filter(user=self.request.user)\
                             .order_by('next_payday')


# ════════════════════════════════════════════════════════════════
# 4.  Comptes
# ════════════════════════════════════════════════════════════════
class AccountsView(LoginRequiredMixin, ListView):
    model               = Account
    template_name       = 'fundboard/accounts.html'
    context_object_name = 'accounts'
    login_url           = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx['manual_form'] = ManualAccountForm()
        return ctx


# ════════════════════════════════════════════════════════════════
# 5.  Modales AJAX (Add / Edit / Delete compte)
# ════════════════════════════════════════════════════════════════
class AjaxModalMixin:
    template_name_fragment = None

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET" and request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return HttpResponseForbidden("Modal uniquement.")
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **resp_kwargs):
        html = render_to_string(self.template_name_fragment, context, self.request)
        return HttpResponse(html)


class AccountSourceModal(AjaxModalMixin, TemplateView):
    template_name_fragment = 'fundboard/modals/account_source.html'


class AddAccountModal(AjaxModalMixin, CreateView):
    model                  = Account
    form_class             = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url            = reverse_lazy('fundboard:accounts')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Compte ajouté.")
        return super().form_valid(form)


class EditAccountModal(AjaxModalMixin, UpdateView):
    model                  = Account
    form_class             = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url            = reverse_lazy('fundboard:accounts')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Compte mis à jour.")
        return super().form_valid(form)


class DeleteAccountModal(AjaxModalMixin, DeleteView):
    model                  = Account
    template_name_fragment = 'fundboard/modals/account_delete.html'
    success_url            = reverse_lazy('fundboard:accounts')

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def delete(self, request, *a, **kw):
        messages.success(request, "Compte supprimé.")
        return super().delete(request, *a, **kw)

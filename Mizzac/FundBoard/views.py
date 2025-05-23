# FundBoard/views.py
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
    CompteBancaire, InvestmentAccount, Transaction,
    Abonnement, Revenu
)
from .forms import AbonnementForm, ManualAccountForm

# ========== Dashboard & pages classiques =========================
class FundBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/fundboard.html'
    login_url = reverse_lazy('fundboard:login')

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        user = self.request.user
        ctx.update(
            accounts_count           = CompteBancaire.objects.filter(user=user).count(),
            investment_accounts_count= InvestmentAccount.objects.filter(user=user).count(),
            transactions_count       = Transaction.objects.filter(user=user).count(),
            subscriptions_count      = Abonnement.objects.filter(user=user).count(),
            recent_transactions      = Transaction.objects.filter(user=user).order_by('-date_transaction')[:5],
            total_balance            = CompteBancaire.objects.filter(user=user).aggregate(Sum('solde'))['solde__sum'] or 0
        )
        return ctx

class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/portfolio.html'
    login_url = reverse_lazy('fundboard:login')
    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx['investment_accounts'] = InvestmentAccount.objects.filter(user=self.request.user)
        return ctx

class TransactionsView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'fundboard/transactions.html'
    context_object_name = 'transactions'
    login_url = reverse_lazy('fundboard:login')
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-date_transaction')

class SubscriptionsView(LoginRequiredMixin, ListView):
    model = Abonnement
    template_name = 'fundboard/subscriptions.html'
    context_object_name = 'subscriptions'
    login_url = reverse_lazy('fundboard:login')
    def get_queryset(self):
        return Abonnement.objects.filter(user=self.request.user).order_by('date_prochaine_echeance')
    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        freq = Abonnement.objects.filter(user=self.request.user).values('frequence').annotate(total=Sum('montant'))
        ctx['labels'] = [f['frequence'].title() for f in freq]
        ctx['data']   = [f['total'] for f in freq]
        return ctx
    
    # ---------- CRUD Abonnement simples (pas en modal pour l’instant) ----------
class AddSubscriptionView(LoginRequiredMixin, CreateView):
    model         = Abonnement
    form_class    = AbonnementForm
    template_name = 'fundboard/subscriptions_form.html'
    success_url   = reverse_lazy('fundboard:subscriptions')
    login_url     = reverse_lazy('fundboard:login')
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Abonnement ajouté.")
        return super().form_valid(form)

class EditSubscriptionView(LoginRequiredMixin, UpdateView):
    model         = Abonnement
    form_class    = AbonnementForm
    template_name = 'fundboard/subscriptions_form.html'
    success_url   = reverse_lazy('fundboard:subscriptions')
    login_url     = reverse_lazy('fundboard:login')
    def get_queryset(self):
        return Abonnement.objects.filter(user=self.request.user)
    def form_valid(self, form):
        messages.success(self.request, "Abonnement mis à jour.")
        return super().form_valid(form)

class DeleteSubscriptionView(LoginRequiredMixin, DeleteView):
    model         = Abonnement
    template_name = 'fundboard/subscriptions_delete.html'
    success_url   = reverse_lazy('fundboard:subscriptions')
    login_url     = reverse_lazy('fundboard:login')
    def get_queryset(self):
        return Abonnement.objects.filter(user=self.request.user)
    def delete(self, request, *a, **kw):
        messages.success(request, "Abonnement supprimé.")
        return super().delete(request, *a, **kw)

# Revenues View
class RevenuesView(LoginRequiredMixin, ListView):
    model = Revenu
    template_name = 'fundboard/revenues.html'
    context_object_name = 'revenues'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Revenu.objects.filter(user=self.request.user).order_by('date_prochain_paiement')

# ------------ Comptes (liste) -----------------------------------
class AccountsView(LoginRequiredMixin, ListView):
    model = CompteBancaire
    template_name = 'fundboard/accounts.html'
    context_object_name = 'accounts'
    login_url = reverse_lazy('fundboard:login')
    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)
    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx['manual_form'] = ManualAccountForm()
        return ctx


# =================================================================
#               MIXIN & VUES MODALES (AJAX only)                   =
# =================================================================
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
    template_name_fragment = "fundboard/modals/account_source.html"

class AddAccountModal(AjaxModalMixin, CreateView):
    model = CompteBancaire
    form_class = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url = reverse_lazy('fundboard:accounts')
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Compte ajouté !")
        return super().form_valid(form)

class EditAccountModal(AjaxModalMixin, UpdateView):
    model = CompteBancaire
    form_class = ManualAccountForm
    template_name_fragment = 'fundboard/modals/account_form.html'
    success_url = reverse_lazy('fundboard:accounts')
    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)
    def form_valid(self, form):
        messages.success(self.request, "Compte mis à jour.")
        return super().form_valid(form)

class DeleteAccountModal(AjaxModalMixin, DeleteView):
    model = CompteBancaire
    template_name_fragment = 'fundboard/modals/account_delete.html'
    success_url = reverse_lazy('fundboard:accounts')
    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)
    def delete(self, request, *a, **kw):
        messages.success(request, "Compte supprimé.")
        return super().delete(request, *a, **kw)

# FundBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import CompteBancaire, Transaction, Abonnement, Revenu

# FundBoard Dashboard View
class FundBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/dashboard.html'
    login_url = reverse_lazy('fundboard:login')

# Portfolio View
class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = 'fundboard/portfolio.html'
    login_url = reverse_lazy('fundboard:login')

# Transactions View
class TransactionsView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'fundboard/transactions.html'
    context_object_name = 'transactions'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-date_transaction')

# Subscriptions View
class SubscriptionsView(LoginRequiredMixin, ListView):
    model = Abonnement
    template_name = 'fundboard/subscriptions.html'
    context_object_name = 'subscriptions'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Abonnement.objects.filter(user=self.request.user).order_by('date_prochaine_echeance')

class AddSubscriptionView(LoginRequiredMixin, CreateView):
    model = Abonnement
    fields = ['nom', 'montant', 'frequence', 'date_prochaine_echeance']
    template_name = 'fundboard/add_subscription.html'
    success_url = reverse_lazy('fundboard:subscriptions')
    login_url = reverse_lazy('fundboard:login')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

# Revenues View
class RevenuesView(LoginRequiredMixin, ListView):
    model = Revenu
    template_name = 'fundboard/revenues.html'
    context_object_name = 'revenues'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Revenu.objects.filter(user=self.request.user).order_by('date_prochain_paiement')

# Comptes Bancaires Views
class AccountsView(LoginRequiredMixin, ListView):
    model = CompteBancaire
    template_name = 'fundboard/accounts.html'
    context_object_name = 'accounts'
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)

class AddAccountView(LoginRequiredMixin, CreateView):
    model = CompteBancaire
    fields = ['nom', 'solde', 'devise']
    template_name = 'fundboard/add_account.html'
    success_url = reverse_lazy('fundboard:accounts')
    login_url = reverse_lazy('fundboard:login')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class EditAccountView(LoginRequiredMixin, UpdateView):
    model = CompteBancaire
    fields = ['nom', 'solde', 'devise']
    template_name = 'fundboard/edit_account.html'
    success_url = reverse_lazy('fundboard:accounts')
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)

class DeleteAccountView(LoginRequiredMixin, DeleteView):
    model = CompteBancaire
    template_name = 'fundboard/delete_account.html'
    success_url = reverse_lazy('fundboard:accounts')
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)

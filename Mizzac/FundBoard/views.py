# FundBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import CompteBancaire, Transaction, Abonnement, Revenu, Asset, InvestmentAccount, SuiviAsset, ListeSuivi
from .forms import AbonnementForm
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.contrib import messages

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Calcul des dépenses par fréquence
        frequency_data = Abonnement.objects.filter(user=self.request.user).values('frequence').annotate(total=Sum('montant'))
        labels = [item['frequence'].title() for item in frequency_data]
        data = [item['total'] for item in frequency_data]
        context['labels'] = labels
        context['data'] = data
        return context

# Add Subscription View
class AddSubscriptionView(LoginRequiredMixin, CreateView):
    model = Abonnement
    form_class = AbonnementForm
    template_name = 'fundboard/add_subscription.html'
    success_url = reverse_lazy('fundboard:subscriptions')
    login_url = reverse_lazy('fundboard:login')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Abonnement ajouté avec succès!')
        return super().form_valid(form)

# Edit Subscription View
class EditSubscriptionView(LoginRequiredMixin, UpdateView):
    model = Abonnement
    form_class = AbonnementForm
    template_name = 'fundboard/edit_subscription.html'
    success_url = reverse_lazy('fundboard:subscriptions')
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Abonnement.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Abonnement mis à jour avec succès!')
        return super().form_valid(form)

# Delete Subscription View
class DeleteSubscriptionView(LoginRequiredMixin, DeleteView):
    model = Abonnement
    template_name = 'fundboard/delete_subscription.html'
    success_url = reverse_lazy('fundboard:subscriptions')
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return Abonnement.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Abonnement supprimé avec succès!')
        return super().delete(request, *args, **kwargs)

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
        messages.success(self.request, 'Compte bancaire ajouté avec succès!')
        return super().form_valid(form)

class EditAccountView(LoginRequiredMixin, UpdateView):
    model = CompteBancaire
    fields = ['nom', 'solde', 'devise']
    template_name = 'fundboard/edit_account.html'
    success_url = reverse_lazy('fundboard:accounts')
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Compte bancaire mis à jour avec succès!')
        return super().form_valid(form)

class DeleteAccountView(LoginRequiredMixin, DeleteView):
    model = CompteBancaire
    template_name = 'fundboard/delete_account.html'
    success_url = reverse_lazy('fundboard:accounts')
    login_url = reverse_lazy('fundboard:login')

    def get_queryset(self):
        return CompteBancaire.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Compte bancaire supprimé avec succès!')
        return super().delete(request, *args, **kwargs)


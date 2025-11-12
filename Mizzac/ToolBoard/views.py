# ToolBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Tool, Category
from django.db.models import Q
from django.shortcuts import render
import ipaddress
import requests
import random
import string
import base64

class ToolBoardView(LoginRequiredMixin, ListView):
    template_name = 'pages/toolboard.html'
    login_url = reverse_lazy('dashboard:login')
    model = Tool
    context_object_name = 'tools'

    def get_queryset(self):
        queryset = super().get_queryset()
        category_name = self.request.GET.get('category')
        search_query = self.request.GET.get('search')

        if category_name:
            queryset = queryset.filter(category__name=category_name)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

class ToolDetailView(LoginRequiredMixin, DetailView):
    model = Tool
    template_name = 'pages/tool_detail.html'
    login_url = reverse_lazy('dashboard:login')
    context_object_name = 'tool'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_tools'] = self.object.related_tools.all()
        return context


# Calculatrice IP
class IPCalculatorView(LoginRequiredMixin, TemplateView):
    template_name = 'tools/ip_calculator.html'
    login_url = reverse_lazy('dashboard:login')

    def post(self, request, *args, **kwargs):
        ip_address = request.POST.get('ip_address')
        subnet_mask = request.POST.get('subnet_mask')
        result = None
        if ip_address and subnet_mask:
            try:
                network = ipaddress.IPv4Network(f"{ip_address}/{subnet_mask}", strict=False)
                result = {
                    'network_address': str(network.network_address),
                    'broadcast_address': str(network.broadcast_address),
                    'num_hosts': network.num_addresses - 2,
                    'wildcard_mask': str(network.hostmask),
                    'mask_bits': network.prefixlen,
                }
            except ValueError:
                result = {'error': 'Adresse IP ou masque invalide'}
        return self.render_to_response({'result': result})

# Convertisseur de devises
class CurrencyConverterView(LoginRequiredMixin, TemplateView):
    template_name = 'tools/currency_converter.html'
    login_url = reverse_lazy('dashboard:login')

    def post(self, request, *args, **kwargs):
        amount = request.POST.get('amount')
        from_currency = request.POST.get('from_currency')
        to_currency = request.POST.get('to_currency')
        result = None
        if amount and from_currency and to_currency:
            try:
                amount = float(amount)
                # Utilisez une API tierce pour obtenir les taux de change
                response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{from_currency}')
                data = response.json()
                rate = data['rates'][to_currency]
                result = amount * rate
            except Exception as e:
                result = {'error': 'Erreur lors de la conversion'}
        return self.render_to_response({'result': result, 'amount': amount, 'from_currency': from_currency, 'to_currency': to_currency})

# Calculatrice de TVA
class VATCalculatorView(LoginRequiredMixin, TemplateView):
    template_name = 'tools/vat_calculator.html'
    login_url = reverse_lazy('dashboard:login')

    def post(self, request, *args, **kwargs):
        amount = request.POST.get('amount')
        vat_rate = request.POST.get('vat_rate')
        result = None
        if amount and vat_rate:
            try:
                amount = float(amount)
                vat_rate = float(vat_rate)
                vat_amount = amount * vat_rate / 100
                total_amount = amount + vat_amount
                result = {
                    'vat_amount': vat_amount,
                    'total_amount': total_amount
                }
            except ValueError:
                result = {'error': 'Montant ou taux de TVA invalide'}
        return self.render_to_response({'result': result})

# Générateur de mots de passe
class PasswordGeneratorView(LoginRequiredMixin, TemplateView):
    template_name = 'tools/password_generator.html'
    login_url = reverse_lazy('dashboard:login')

    def post(self, request, *args, **kwargs):
        length = request.POST.get('length')
        include_uppercase = 'include_uppercase' in request.POST
        include_numbers = 'include_numbers' in request.POST
        include_symbols = 'include_symbols' in request.POST
        password = ''
        if length:
            try:
                length = int(length)
                characters = string.ascii_lowercase
                if include_uppercase:
                    characters += string.ascii_uppercase
                if include_numbers:
                    characters += string.digits
                if include_symbols:
                    characters += string.punctuation
                password = ''.join(random.choice(characters) for _ in range(length))
            except ValueError:
                password = 'Longueur invalide'
        return self.render_to_response({'password': password})

# Encodeur/Décodeur Base64
class Base64ConverterView(LoginRequiredMixin, TemplateView):
    template_name = 'tools/base64_converter.html'
    login_url = reverse_lazy('dashboard:login')

    def post(self, request, *args, **kwargs):
        text = request.POST.get('text')
        action = request.POST.get('action')
        result = ''
        if text and action:
            try:
                if action == 'encode':
                    result = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                elif action == 'decode':
                    result = base64.b64decode(text.encode('utf-8')).decode('utf-8')
            except Exception:
                result = 'Erreur lors de la conversion'
        return self.render_to_response({'result': result})

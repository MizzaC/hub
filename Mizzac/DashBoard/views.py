# Mizzac/Dashboard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import CustomUserCreationForm
from django.shortcuts import render

def home(request):
    return render(request, 'dashboard.html')


# Homepage view (The HUB)
class HubView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/hub.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected
    # further features or requirements

# SignUp view
class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'dashboard/signup.html'
    success_url = reverse_lazy('dashboard:login')  # Redirect after successfull connexion

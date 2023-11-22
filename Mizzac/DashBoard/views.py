# Mizzac/Dashboard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import CustomUserCreationForm



# Homepage view (The HUB)
class HubView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/dashboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected
    # further features or requirements

# SignUp view
class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'pages/signup.html'
    success_url = reverse_lazy('dashboard:login')  # Redirect after successfull connexion

from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import generic
from .forms import CustomUserCreationForm

class SignUpView(generic.CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')  # Assurez-vous que l'URL 'login' est définie dans urls.py
    template_name = 'dashboard/signup.html'  # Le chemin du template d'inscription

class LogInView(generic.CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('admin')  # Assurez-vous que l'URL 'login' est définie dans urls.py
    template_name = 'dashboard/login.html'  # Le chemin du template d'inscription
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import generic
from .forms import CustomUserCreationForm

class SignUpView(generic.CreateView):
    form_class = CustomUserCreationForm
    #success_url = reverse_lazy('login')  # Assurez-vous que l'URL 'login' est définie dans urls.py
    template_name = 'signup.html'  # Le chemin du template d'inscription

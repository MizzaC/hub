# Mizzac/ToolBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

# ToolBoard view
class ToolBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/toolboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected

# Mizzac/GameBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin



    
# GameBoard view
class GameBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/gameboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected
    # further features or requirements
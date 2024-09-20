# Mizzac/GameBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Game, Category

# GameBoard view
class GameBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/gameboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['games'] = Game.objects.all()  # Retrieve all games
        context['categories'] = Category.objects.all()  # Retrieve all categories
        return context

class GameDetailView(LoginRequiredMixin, DetailView):
    model = Game
    template_name = 'pages/game_detail.html'
    context_object_name = 'game'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

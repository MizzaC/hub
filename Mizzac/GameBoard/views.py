# Mizzac/GameBoard/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, TemplateView

from .models import Category, ChessSave, Game, NavalBattleSave, SkyJoSave, TicTacToeSave


# GameBoard view
class GameBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/gameboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['games'] = Game.objects.prefetch_related("categories").order_by("name")
        context['categories'] = Category.objects.all()  # Retrieve all categories
        return context

class GameDetailView(LoginRequiredMixin, DetailView):
    model = Game
    template_name = 'pages/game_detail.html'
    context_object_name = 'game'
    slug_field = 'game_slug'
    slug_url_kwarg = 'game_slug'

class GameSaveView(LoginRequiredMixin, View):
    template_map = {
        'skyjo': {
            'model': SkyJoSave,
            'template': 'pages/games/skyjo.html',
        },
        'navalbattle': {
            'model': NavalBattleSave,
            'template': 'pages/games/naval_battle.html',
        },
        'tictactoe': {
            'model': TicTacToeSave,
            'template': 'pages/games/tic_tac_toe.html',
        },
        'chess': {
            'model': ChessSave,
            'template': 'pages/games/chess.html',
        },
    }

    login_url = reverse_lazy('dashboard:login')  # If user not connected

    def get(self, request, game_slug, save_slug):
        game = get_object_or_404(Game, game_slug=game_slug)
        game_key = game.name.lower()  # Assuming game names match keys in template_map

        if game_key in self.template_map:
            save_model = self.template_map[game_key]['model']
            template_name = self.template_map[game_key]['template']
            save_instance = get_object_or_404(save_model, id=save_slug)
            context = {
                'game': game,
                'save': save_instance,
            }
            return render(request, template_name, context)
        else:
            return render(request, 'pages/error.html', {'message': 'Game not supported.'})

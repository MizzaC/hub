# Mizzac/Dashboard/urls.py

from django.urls import path

from .views import GameBoardView, GameDetailView, GameSaveView

app_name = 'gameboard'

urlpatterns = [
    
    # GameBoard Homepage
    path('', GameBoardView.as_view(), name='gameboard'),

    path('game/<slug:game_slug>/detail', GameDetailView.as_view(), name='game_detail'),
    path('game/<slug:game_slug>/<slug:save_slug>/', GameSaveView.as_view(), name='game_save'),

]

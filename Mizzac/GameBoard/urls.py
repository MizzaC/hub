# Mizzac/Dashboard/urls.py

from django.urls import path
from .views import GameBoardView
from django.contrib.auth import views as auth_views


app_name = 'gameboard'

urlpatterns = [
    
    # GameBoard Homepage
    path('', GameBoardView.as_view(), name='gameboard'),

]

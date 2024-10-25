# Mizzac/ToolBoard/urls.py

from django.urls import path
from .views import ToolBoardView
from django.contrib.auth import views as auth_views

app_name = 'toolboard'

urlpatterns = [
        
    # DrunkBoard Homepage
    path('', ToolBoardView.as_view(), name='toolboard'),

]
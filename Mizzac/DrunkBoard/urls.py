# Mizzac/Dashboard/urls.py

from django.urls import path
from .views import DrunkBoardView
from django.contrib.auth import views as auth_views


app_name = 'drunkboard'

urlpatterns = [
    
    # DrunkBoard Homepage
    path('', DrunkBoardView.as_view(), name='drunkboard'),

]

# Mizzac/Dashboard/urls.py

from django.urls import path

from .views import DrunkBoardView

app_name = 'drunkboard'

urlpatterns = [
    
    # DrunkBoard Homepage
    path('', DrunkBoardView.as_view(), name='drunkboard'),

]

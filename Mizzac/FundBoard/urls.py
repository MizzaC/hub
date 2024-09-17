# Mizzac/Dashboard/urls.py

from django.urls import path
from .views import FundBoardView
from django.contrib.auth import views as auth_views


app_name = 'fundboard'

urlpatterns = [
    
    # DrunkBoard Homepage
    path('', FundBoardView.as_view(), name='fundboard'),

]

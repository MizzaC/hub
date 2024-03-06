# Mizzac/Dashboard/urls.py

from django.urls import path
from .views import SignUpView, HubView, DrunkBoardView
from django.contrib.auth import views as auth_views


app_name = 'dashboard'

urlpatterns = [
    # DashBoard Homepage (The HUB)
    path('', HubView.as_view(), name='dashboard'),
    
    # DrunkBoard Homepage
    path('drunkboard/', DrunkBoardView.as_view(), name='drunkboard'),

    # Login URL
    path('login/', auth_views.LoginView.as_view(template_name='pages/login.html'), name='login'),

    # Logout URL
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Signup URL
    path('signup/', SignUpView.as_view(), name='signup'),

]

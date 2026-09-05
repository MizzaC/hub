# Mizzac/Dashboard/urls.py

from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import StyledAuthenticationForm
from .views import HubView, SignUpView

app_name = 'dashboard'

urlpatterns = [
    # DashBoard Homepage (The HUB)
    path('', HubView.as_view(), name='dashboard'),

    # Login URL
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="common/login.html",
            authentication_form=StyledAuthenticationForm,
        ),
        name="login",
    ),

    # Logout URL
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Signup URL
    path('signup/', SignUpView.as_view(), name='signup'),

]

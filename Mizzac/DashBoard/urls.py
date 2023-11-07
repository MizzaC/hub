from django.urls import path
from .views import SignUpView

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('signup/', SignUpView.as_view(), name='signup'),

]

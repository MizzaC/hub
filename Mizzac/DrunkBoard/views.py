# Mizzac/Dashboard/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView


# DrunkBoard view
class DrunkBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/drunkboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected
    # further features or requirements


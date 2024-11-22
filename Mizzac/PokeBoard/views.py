# Mizzac/PokeBoard/views.py

from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from .models import UserCollection, Card, UserCard
from .forms import UserCollectionForm


# PokeBoard view
class PokeBoardView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/pokeboard.html'
    login_url = reverse_lazy('dashboard:login')  # If user not connected
    # further features or requirements

def add_card_to_collection(request, collection_id, card_id):
    user_collection = get_object_or_404(UserCollection, id=collection_id, user=request.user)
    card = get_object_or_404(Card, id=card_id)

    user_card, created = UserCard.objects.get_or_create(
        user_collection=user_collection,
        card=card,
        defaults={'quantity': 1}
    )
    if not created:
        user_card.quantity += 1
        user_card.save()

    return redirect('pokeboard:usercollection_detail', pk=user_collection.id)

class UserCollectionCreateView(LoginRequiredMixin, CreateView):
    model = UserCollection
    form_class = UserCollectionForm
    template_name = 'pages/create_usercollection.html'
    success_url = reverse_lazy('pokeboard:pokeboard')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class UserCollectionDetailView(LoginRequiredMixin, DetailView):
    model = UserCollection
    template_name = 'pages/usercollection_detail.html'
    context_object_name = 'user_collection'

    def get_queryset(self):
        return UserCollection.objects.filter(user=self.request.user)
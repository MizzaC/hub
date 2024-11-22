# Mizzac/PokeBoard/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    PokeBoardView,
    UserCollectionCreateView,
    UserCollectionDetailView,
    add_card_to_collection,
)

app_name = 'pokeboard'

urlpatterns = [
    path('', PokeBoardView.as_view(), name='pokeboard'),
    path('collections/create/', UserCollectionCreateView.as_view(), name='create_usercollection'),
    path('collections/<int:pk>/', UserCollectionDetailView.as_view(), name='usercollection_detail'),
    path('collections/<int:collection_id>/add_card/<int:card_id>/', add_card_to_collection, name='add_card_to_collection'),
]
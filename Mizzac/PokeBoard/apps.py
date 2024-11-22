from django.apps import AppConfig
from pokemontcgsdk import RestClient

class PokeboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "PokeBoard"
    
    def ready(self):
        RestClient.configure("settings.POKEMON_TCG_API_KEY")
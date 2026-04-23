from django.apps import AppConfig
from django.conf import settings


class PokeboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "PokeBoard"
    verbose_name = "PokeBoard"

    def ready(self):
        api_key = getattr(settings, "POKEMON_TCG_API_KEY", "")
        if not api_key:
            return

        try:
            from pokemontcgsdk import RestClient
        except Exception:
            return

        RestClient.configure(api_key)


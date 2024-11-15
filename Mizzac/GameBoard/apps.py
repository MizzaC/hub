from django.apps import AppConfig


class GameboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'GameBoard'
    
    def ready(self):
        import GameBoard.signals

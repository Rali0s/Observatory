from django.apps import AppConfig

class StudioConfig(AppConfig):
    name='studio'
    default_auto_field='django.db.models.BigAutoField'
    def ready(self):
        from . import achievement_signals

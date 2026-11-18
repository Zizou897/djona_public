from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'Suivi en temps réel'

    def ready(self):
        from . import signals  # noqa: F401 — branche les événements métier

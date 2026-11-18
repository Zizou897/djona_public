from django.apps import AppConfig


class AnalyticsLiveConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics_live'
    verbose_name = 'Temps réel'

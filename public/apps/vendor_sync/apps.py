from django.apps import AppConfig


class VendorSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.vendor_sync'
    label = 'vendor_sync'
    verbose_name = 'Synchronisation vendor'

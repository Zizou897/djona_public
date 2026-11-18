from . import tracking
from django.conf import settings


def analytics(request):
    """Clé du site pour le script de suivi ; vide (script non inséré) tant que ANALYTICS_SITE_KEY n'est pas défini."""
    return {'analytics_site_key': settings.ANALYTICS_SITE_KEY if tracking.enabled() else ''}

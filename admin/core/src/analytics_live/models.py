from django.db import models
from django.utils import timezone

# Sites suivis → alias de la base qui porte leurs tables `analytics_*` (créées et migrées par le projet du site,
# lues ici via des modèles miroirs `managed=False`, comme moderation/contactmessages).
SITES = {
    'public': {'label': 'Site public', 'alias': 'public_db'},
    'vendor': {'label': 'Espace vendeur', 'alias': 'vendor_db'},
}


class EventMirror(models.Model):
    """Miroir de analytics.Event (table analytics_event) du projet public OU vendor : choisir l'alias avec `.using()`."""

    site = models.CharField(max_length=20)
    type = models.CharField(max_length=10)
    name = models.CharField(max_length=60, blank=True)
    path = models.CharField(max_length=255, blank=True)
    session_id = models.CharField(max_length=40, blank=True)
    device = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=2, blank=True)
    ip_anon = models.CharField(max_length=45, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'analytics_event'
        ordering = ['-id']


class PresenceMirror(models.Model):
    """Miroir de analytics.Presence : dernière activité (heartbeat) de chaque session."""

    session_id = models.CharField(max_length=40, primary_key=True)
    site = models.CharField(max_length=20)
    path = models.CharField(max_length=255, blank=True)
    device = models.CharField(max_length=10, blank=True)
    last_seen = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'analytics_presence'


class AlertState(models.Model):
    """État d'une alerte (propre à l'admin, base `default`) : anti-spam (délai entre deux envois) et message de
    résolution quand tout redevient normal. Une ligne par (site, type d'alerte)."""

    key = models.CharField(max_length=60, unique=True)     # ex. « public:erreurs_5xx »
    active = models.BooleanField(default=False)
    failures = models.PositiveIntegerField(default=0)      # échecs consécutifs (ping de santé)
    since = models.DateTimeField(null=True, blank=True)    # début de l'incident en cours
    last_sent_at = models.DateTimeField(null=True, blank=True)
    detail = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.key} ({"active" if self.active else "ok"})'

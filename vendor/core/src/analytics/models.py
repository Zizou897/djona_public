"""Suivi du trafic en temps réel — consulté en lecture depuis le back-office (projet admin,
modèles miroirs `analytics_live.models`). Ce projet possède et migre les tables ; le back-office ne fait que lire.

Aucune donnée personnelle : pas d'IP complète (dernier octet tronqué), pas de corps de formulaire,
pas de numéro de téléphone — seulement des chemins, des statuts, des durées et un identifiant de session aléatoire.
"""
from django.db import models
from django.utils import timezone


class Event(models.Model):
    class Type(models.TextChoices):
        PAGEVIEW = 'pageview', 'Page vue'        # envoyé par le script du navigateur (visiteurs réels)
        REQUEST = 'request', 'Requête serveur'   # écrit par le middleware (statut HTTP, durée)
        ACTION = 'action', 'Action métier'       # inscription, demande, commande, recherche…

    site = models.CharField(max_length=20, default='vendor')
    type = models.CharField(max_length=10, choices=Type.choices)
    name = models.CharField('action', max_length=60, blank=True)
    path = models.CharField(max_length=255, blank=True)
    session_id = models.CharField(max_length=40, blank=True)
    device = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=2, blank=True)
    ip_anon = models.CharField(max_length=45, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['type', 'created_at'], name='analytics_type_created_idx'),
            models.Index(fields=['site', 'type', 'created_at'], name='analytics_site_type_idx'),
            models.Index(fields=['name', 'created_at'], name='analytics_name_created_idx'),
            models.Index(fields=['session_id'], name='analytics_session_idx'),
        ]

    def __str__(self):
        return f'{self.type} {self.name or self.path}'


class Presence(models.Model):
    """Dernière activité (heartbeat toutes les ~15 s) d'une session : « visiteurs en ligne » = last_seen < 60 s.
    Une ligne par session (et non une par battement) pour que la table reste petite."""

    session_id = models.CharField(max_length=40, primary_key=True)
    site = models.CharField(max_length=20, default='vendor')
    path = models.CharField(max_length=255, blank=True)
    device = models.CharField(max_length=10, blank=True)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return self.session_id


class DailyStat(models.Model):
    """Agrégats journaliers, conservés après la purge des événements détaillés."""

    site = models.CharField(max_length=20, default='vendor')
    date = models.DateField()
    pageviews = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    actions = models.PositiveIntegerField(default=0)
    requests = models.PositiveIntegerField(default=0)
    errors_4xx = models.PositiveIntegerField(default=0)
    errors_5xx = models.PositiveIntegerField(default=0)
    avg_duration_ms = models.PositiveIntegerField(default=0)
    p95_duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-date']
        constraints = [models.UniqueConstraint(fields=['site', 'date'], name='analytics_dailystat_site_date_uniq')]

    def __str__(self):
        return f'{self.site} {self.date}'

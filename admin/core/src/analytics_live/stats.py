"""Calculs du tableau « Temps réel » (et des alertes) à partir des tables `analytics_*` d'un site.

Tout passe par l'ORM sans fonction de date SQL (pas de TruncMinute/TruncDate : sous MySQL ils exigent les tables de
fuseaux horaires) : les regroupements par minute se font en Python sur des fenêtres courtes.
"""
import math
from collections import Counter
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import EventMirror, PresenceMirror, SITES

ONLINE_WINDOW = timedelta(seconds=60)
CHART_MINUTES = 30
RATE_WINDOW = timedelta(minutes=15)
TOP_LIMIT = 8
FEED_LIMIT = 40
MAX_LATENCY_SAMPLES = 5000

ACTION_LABELS = {
    'message_contact': 'Message de contact',
    'demande_transport': 'Demande de transport',
    'demande_piece': 'Demande de pièce',
    'commande_piece': 'Commande de pièces',
    'inscription_newsletter': 'Inscription newsletter',
    'interet_vehicule': 'Intérêt pour un véhicule',
    'demande_location': 'Demande de location',
    'recherche_vehicule': 'Recherche de véhicule',
    'recherche_piece': 'Recherche de pièce',
    'vehicule_vu': 'Fiche véhicule consultée',
    'piece_vue': 'Fiche pièce consultée',
    'panier_ajout': 'Ajout au panier',
    'clic_whatsapp': 'Clic WhatsApp',
    'clic_telephone': 'Clic téléphone',
}
DEVICE_LABELS = {'mobile': 'Mobile', 'desktop': 'Ordinateur', 'tablet': 'Tablette', '': 'Inconnu'}


def action_label(name):
    return ACTION_LABELS.get(name, name.replace('_', ' ').capitalize())


def alias_for(site):
    return SITES[site]['alias']


def percentile(values, pct):
    """Percentile « rang le plus proche » d'une liste triée (0 si vide)."""
    if not values:
        return 0
    return values[min(max(math.ceil(pct / 100 * len(values)) - 1, 0), len(values) - 1)]


def start_of_today(now=None):
    return timezone.localtime(now or timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)


def online_count(alias, now=None):
    now = now or timezone.now()
    return PresenceMirror.objects.using(alias).filter(last_seen__gte=now - ONLINE_WINDOW).count()


def pageviews_by_minute(alias, now=None, minutes=CHART_MINUTES):
    """`minutes` compteurs de pages vues, du plus ancien au plus récent (la dernière valeur = minute en cours)."""
    now = now or timezone.now()
    current = now.replace(second=0, microsecond=0)
    first = current - timedelta(minutes=minutes - 1)
    stamps = EventMirror.objects.using(alias).filter(type='pageview', created_at__gte=first).values_list('created_at', flat=True)
    buckets = Counter(int((stamp - first).total_seconds() // 60) for stamp in stamps)
    return [
        {'minute': timezone.localtime(first + timedelta(minutes=i)).strftime('%H:%M'), 'count': buckets.get(i, 0)}
        for i in range(minutes)
    ]


def request_health(alias, window=RATE_WINDOW, now=None):
    """Volume, erreurs et temps de réponse des requêtes serveur sur la fenêtre."""
    now = now or timezone.now()
    requests = EventMirror.objects.using(alias).filter(type='request', created_at__gte=now - window)
    total = requests.count()
    errors_4xx = requests.filter(status_code__gte=400, status_code__lt=500).count()
    errors_5xx = requests.filter(status_code__gte=500).count()
    durations = sorted(
        requests.exclude(duration_ms__isnull=True).order_by('-id').values_list('duration_ms', flat=True)[:MAX_LATENCY_SAMPLES]
    )
    return {
        'total': total,
        'errors_4xx': errors_4xx,
        'errors_5xx': errors_5xx,
        'rate_4xx': round(100 * errors_4xx / total, 1) if total else 0,
        'rate_5xx': round(100 * errors_5xx / total, 1) if total else 0,
        'avg_ms': int(sum(durations) / len(durations)) if durations else 0,
        'p95_ms': percentile(durations, 95),
    }


def _ranked(queryset, field, limit=None):
    rows = queryset.values(field).annotate(n=Count('id')).order_by('-n')
    return list(rows[:limit] if limit else rows)


def snapshot(site, now=None):
    """Tout le contenu du tableau de bord pour un site."""
    alias = alias_for(site)
    now = now or timezone.now()
    today = EventMirror.objects.using(alias).filter(created_at__gte=start_of_today(now))
    pageviews = today.filter(type='pageview')

    actions = [
        {'name': row['name'], 'label': action_label(row['name']), 'count': row['n']}
        for row in _ranked(today.filter(type='action'), 'name')
    ]
    top_pages = [{'path': row['path'], 'count': row['n']} for row in _ranked(pageviews, 'path', TOP_LIMIT)]
    devices = [{'name': DEVICE_LABELS.get(row['device'], row['device']), 'count': row['n']} for row in _ranked(pageviews, 'device')]
    countries = [{'name': row['country'], 'count': row['n']} for row in _ranked(pageviews.exclude(country=''), 'country', TOP_LIMIT)]
    latest = EventMirror.objects.using(alias).order_by('-id').values_list('id', flat=True).first() or 0

    return {
        'site': site,
        'generated_at': timezone.localtime(now).strftime('%H:%M:%S'),
        'online': online_count(alias, now),
        'pageviews_today': pageviews.count(),
        'visitors_today': pageviews.exclude(session_id='').values('session_id').distinct().count(),
        'actions_today': sum(item['count'] for item in actions),
        'chart': pageviews_by_minute(alias, now),
        'health': request_health(alias, now=now),
        'actions': actions,
        'top_pages': top_pages,
        'devices': devices,
        'countries': countries,
        'latest_id': latest,
    }


def feed(site, since=0, now=None):
    """Flux d'événements notables : actions, pages vues et erreurs (les requêtes 2xx/3xx seraient du bruit)."""
    alias = alias_for(site)
    rows = EventMirror.objects.using(alias).filter(id__gt=since)
    notable = [e for e in rows.exclude(type='request').order_by('-id')[:FEED_LIMIT]]
    errors = [e for e in rows.filter(type='request', status_code__gte=400).order_by('-id')[:FEED_LIMIT]]
    events = sorted(notable + errors, key=lambda e: e.id, reverse=True)[:FEED_LIMIT]

    items = []
    for event in events:
        if event.type == 'action':
            kind, label = 'action', action_label(event.name)
        elif event.type == 'pageview':
            kind, label = 'pageview', 'Page vue'
        else:
            kind = 'error5xx' if (event.status_code or 0) >= 500 else 'error4xx'
            label = f'Erreur {event.status_code}'
        items.append({
            'id': event.id,
            'time': timezone.localtime(event.created_at).strftime('%H:%M:%S'),
            'kind': kind,
            'label': label,
            'path': event.path,
            'device': DEVICE_LABELS.get(event.device, ''),
            'detail': _detail(event),
        })
    return items


def _detail(event):
    """Courte précision lisible, tirée des métadonnées non personnelles."""
    meta = event.meta if isinstance(event.meta, dict) else {}
    parts = [f'{key} : {value}' for key, value in meta.items() if key not in ('method', 'ref') and value != '']
    if event.type == 'request' and event.duration_ms is not None:
        parts.append(f'{event.duration_ms} ms')
    return ' · '.join(parts)[:160]


def count_pageviews(alias, since, until):
    """Pages vues dans [since, until) — base de comparaison pour la détection de chute de trafic."""
    return EventMirror.objects.using(alias).filter(type='pageview', created_at__gte=since, created_at__lt=until).count()

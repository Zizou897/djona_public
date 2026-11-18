"""Agrégats journaliers (conservés après la purge des événements détaillés)."""
import math
from datetime import datetime, time, timedelta

from django.db.models import Avg
from django.utils import timezone

from .models import DailyStat, Event


def percentile(values, pct):
    """Percentile « rang le plus proche » d'une liste déjà triée (0 si vide)."""
    if not values:
        return 0
    index = max(math.ceil(pct / 100 * len(values)) - 1, 0)
    return values[min(index, len(values) - 1)]


def aggregate_day(day, site):
    """Recalcule (idempotent) la ligne DailyStat de `day` à partir des événements détaillés."""
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)
    events = Event.objects.filter(site=site, created_at__gte=start, created_at__lt=end)

    pageviews = events.filter(type=Event.Type.PAGEVIEW)
    requests = events.filter(type=Event.Type.REQUEST)
    durations = sorted(requests.exclude(duration_ms__isnull=True).values_list('duration_ms', flat=True))

    stat, _ = DailyStat.objects.update_or_create(site=site, date=day, defaults={
        'pageviews': pageviews.count(),
        'visitors': pageviews.exclude(session_id='').values('session_id').distinct().count(),
        'actions': events.filter(type=Event.Type.ACTION).count(),
        'requests': requests.count(),
        'errors_4xx': requests.filter(status_code__gte=400, status_code__lt=500).count(),
        'errors_5xx': requests.filter(status_code__gte=500).count(),
        'avg_duration_ms': int(requests.aggregate(avg=Avg('duration_ms'))['avg'] or 0),
        'p95_duration_ms': percentile(durations, 95),
    })
    return stat

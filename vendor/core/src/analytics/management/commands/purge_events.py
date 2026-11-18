from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.aggregates import aggregate_day
from analytics.models import DailyStat, Event, Presence
from analytics.tracking import site_name


class Command(BaseCommand):
    help = (
        "Agrège les statistiques par jour puis supprime les événements plus anciens que la rétention "
        "(ANALYTICS_RETENTION_DAYS, 90 jours par défaut). À lancer chaque nuit (cron)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None, help="Rétention en jours (défaut : ANALYTICS_RETENTION_DAYS).")

    def handle(self, *args, **options):
        days = options['days'] if options['days'] is not None else settings.ANALYTICS_RETENTION_DAYS
        site = site_name()
        now = timezone.now()
        cutoff = now - timedelta(days=days)

        # La veille est toujours agrégée (historique à jour) ; les jours sur le point d'être purgés le sont avant suppression.
        yesterday = timezone.localdate(now) - timedelta(days=1)
        to_aggregate = {yesterday}
        # Jours à figer avant suppression : de l'événement le plus ancien jusqu'au jour du seuil. On parcourt les
        # dates en Python (pas de TruncDate : sous MySQL il exige les tables de fuseaux horaires).
        oldest = Event.objects.filter(site=site, created_at__lt=cutoff).order_by('created_at').first()
        if oldest:
            day = timezone.localdate(oldest.created_at)
            last = timezone.localdate(cutoff)
            already = set(DailyStat.objects.filter(site=site, date__lte=last).values_list('date', flat=True))
            while day <= last:
                # Un jour déjà agrégé n'est jamais recalculé : ses événements sont peut-être déjà en partie purgés.
                if day not in already:
                    to_aggregate.add(day)
                day += timedelta(days=1)
        for day in sorted(to_aggregate):
            aggregate_day(day, site)

        deleted, _ = Event.objects.filter(site=site, created_at__lt=cutoff).delete()
        stale, _ = Presence.objects.filter(last_seen__lt=now - timedelta(hours=1)).delete()
        self.stdout.write(
            f'{len(to_aggregate)} jour(s) agrégé(s), {deleted} événement(s) supprimé(s) '
            f'(> {days} j), {stale} session(s) inactive(s) nettoyée(s).'
        )

from django.core.management.base import BaseCommand

from analytics_live import alerts


class Command(BaseCommand):
    help = (
        "Évalue les alertes (erreurs 5xx, lenteur, chute de trafic, site inaccessible) et envoie e-mail / Telegram "
        "selon la configuration. À lancer chaque minute (cron ou timer systemd)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Affiche l'état sans rien envoyer ni enregistrer.")

    def handle(self, *args, **options):
        configured = alerts.channels()
        if options['verbosity'] > 1 or options['dry_run']:
            self.stdout.write('Canaux configurés : ' + (', '.join(configured) or 'aucun (rien ne sera envoyé)'))
        for site, condition, action in alerts.run(dry_run=options['dry_run']):
            state = 'PROBLÈME' if condition.problem else 'ok'
            suffix = f' → {action}' if action else ''
            if options['verbosity'] > 1 or options['dry_run'] or action:
                self.stdout.write(f'[{site}] {condition.key}: {state}{suffix} — {condition.detail}')

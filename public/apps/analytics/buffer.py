"""Tampon d'écriture : le suivi ne doit jamais ralentir une requête ni la faire échouer.

Les événements sont empilés en mémoire (O(1), sans accès base) puis écrits par lot (`bulk_create`) par un
fil d'arrière-plan, toutes les ~2 s ou dès que le lot est plein. Un fil par processus gunicorn, démarré
paresseusement à la première requête (donc après le fork). Un processus tué perd au plus ~2 s d'événements :
c'est le prix de ne jamais bloquer le site, et acceptable pour des statistiques.

Pas de Redis ici : le projet n'en utilise pas en production. Si la base est indisponible, le lot est abandonné
(journalisé), jamais retenté en boucle.
"""
import logging
import os
import threading

from django.conf import settings
from django.db import close_old_connections, connection

logger = logging.getLogger(__name__)

FLUSH_INTERVAL = 2.0   # secondes
BATCH_SIZE = 100       # écriture immédiate dès que le lot est plein
MAX_PENDING = 5000     # au-delà (base très lente), les nouveaux événements sont abandonnés


class EventBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = []
        self._presence = {}   # session_id -> Presence (le plus récent gagne)
        self._thread = None
        self._pid = None
        self._wake = threading.Event()
        self._warned = False

    # --- API ---------------------------------------------------------------------------------

    def add_event(self, event):
        self._add(event=event)

    def touch_presence(self, presence):
        self._add(presence=presence)

    def flush(self):
        """Écrit tout ce qui est en attente. Renvoie le nombre d'événements écrits ; ne lève jamais."""
        with self._lock:
            events, presence = self._events, self._presence
            self._events, self._presence = [], {}
        if not events and not presence:
            return 0
        from .models import Event, Presence
        written = 0
        try:
            if events:
                Event.objects.bulk_create(events)
                written = len(events)
            if presence:
                # MySQL (ON DUPLICATE KEY UPDATE) refuse `unique_fields` ; SQLite et PostgreSQL l'exigent.
                options = {'unique_fields': ['session_id']} if connection.features.supports_update_conflicts_with_target else {}
                Presence.objects.bulk_create(
                    list(presence.values()), update_conflicts=True, update_fields=['site', 'path', 'device', 'last_seen'],
                    **options,
                )
        except Exception:
            logger.warning('Suivi : écriture du lot abandonnée (base indisponible ?)', exc_info=True)
        return written

    # --- Interne -----------------------------------------------------------------------------

    def _add(self, event=None, presence=None):
        if not getattr(settings, 'ANALYTICS_ASYNC', True):
            with self._lock:
                if event is not None:
                    self._events.append(event)
                if presence is not None:
                    self._presence[presence.session_id] = presence
            self.flush()
            return
        with self._lock:
            if len(self._events) + len(self._presence) >= MAX_PENDING:
                if not self._warned:
                    logger.warning('Suivi : tampon plein, événements abandonnés')
                    self._warned = True
                return
            self._warned = False
            if event is not None:
                self._events.append(event)
            if presence is not None:
                self._presence[presence.session_id] = presence
            full = len(self._events) + len(self._presence) >= BATCH_SIZE
        self._ensure_thread()
        if full:
            self._wake.set()

    def _ensure_thread(self):
        # Après un fork (gunicorn), le fil du processus parent n'existe plus dans l'enfant : on en recrée un.
        if self._thread is not None and self._pid == os.getpid() and self._thread.is_alive():
            return
        with self._lock:
            if self._thread is not None and self._pid == os.getpid() and self._thread.is_alive():
                return
            self._pid = os.getpid()
            self._wake = threading.Event()
            self._thread = threading.Thread(target=self._run, name='analytics-flush', daemon=True)
            self._thread.start()

    def _run(self):
        wake = self._wake
        while True:
            wake.wait(FLUSH_INTERVAL)
            wake.clear()
            try:
                close_old_connections()  # fil d'arrière-plan uniquement : rend la connexion si elle a expiré
                self.flush()
            except Exception:  # ne jamais laisser mourir le fil
                logger.exception('Suivi : erreur inattendue dans le fil d\'écriture')


buffer = EventBuffer()

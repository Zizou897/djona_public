"""Point d'entrée unique pour enregistrer un événement. Ne lève jamais d'exception vers l'appelant."""
import logging
from contextvars import ContextVar

from django.conf import settings
from django.utils import timezone

from . import utils
from .buffer import buffer
from .models import Event, Presence

logger = logging.getLogger(__name__)

SESSION_COOKIE = 'djona_sid'

# Contexte du visiteur courant (posé par le middleware) : permet aux signaux (création d'une commande, d'un
# message…) de rattacher l'action à la même session, sans passer `request` partout.
_current = ContextVar('djona_analytics_visitor', default=None)


def enabled():
    return bool(getattr(settings, 'ANALYTICS_SITE_KEY', ''))


def site_name():
    return getattr(settings, 'ANALYTICS_SITE_NAME', 'vendor')


def visitor_from_request(request):
    return {
        'session_id': utils.valid_session_id(request.COOKIES.get(SESSION_COOKIE, '')),
        'device': utils.device_from_user_agent(request.META.get('HTTP_USER_AGENT', '')),
        'country': utils.country_from_request(request),
        'ip_anon': utils.anonymize_ip(utils.client_ip(request)),
    }


def set_visitor(visitor):
    return _current.set(visitor)


def reset_visitor(token):
    _current.reset(token)


def record(type_, *, name='', path='', status_code=None, duration_ms=None, meta=None, visitor=None, created_at=None):
    """Empile un événement. `visitor` : dict session_id/device/country/ip_anon (sinon celui de la requête en cours)."""
    if not enabled():
        return
    try:
        visitor = visitor or _current.get() or {}
        buffer.add_event(Event(
            site=site_name(), type=type_, name=name[:60], path=utils.clean_path(path),
            session_id=visitor.get('session_id', ''), device=visitor.get('device', ''),
            country=visitor.get('country', ''), ip_anon=visitor.get('ip_anon', ''),
            status_code=status_code, duration_ms=duration_ms, meta=utils.clean_meta(meta or {}),
            created_at=created_at or timezone.now(),
        ))
    except Exception:
        logger.exception('Suivi : événement ignoré')


def touch_presence(session_id, path, device):
    if not enabled() or not session_id:
        return
    try:
        buffer.touch_presence(Presence(
            session_id=session_id, site=site_name(), path=utils.clean_path(path), device=device,
            last_seen=timezone.now(),
        ))
    except Exception:
        logger.exception('Suivi : présence ignorée')


def track(name, meta=None):
    """Action métier côté serveur : `track('commande_piece', {'reference': 'CMD-1'})`."""
    record(Event.Type.ACTION, name=name, meta=meta)

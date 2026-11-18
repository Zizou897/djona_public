"""Mesure chaque requête (statut, durée) de l'espace vendeur.

Doit rester le premier middleware : il mesure alors toute la pile. Toute erreur de suivi est avalée — le site
ne doit jamais échouer ni ralentir à cause de ses statistiques.
"""
import logging
import time

from . import tracking, utils
from .models import Event

logger = logging.getLogger(__name__)


class AnalyticsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not tracking.enabled():
            return self.get_response(request)

        start = time.monotonic()
        visitor = tracking.visitor_from_request(request)
        token = tracking.set_visitor(visitor)
        try:
            response = self.get_response(request)
        finally:
            tracking.reset_visitor(token)
        try:
            self._record(request, response, visitor, int((time.monotonic() - start) * 1000))
        except Exception:
            logger.exception('Suivi : requête non enregistrée')
        return response

    def _record(self, request, response, visitor, duration_ms):
        if request.method not in ('GET', 'POST'):
            return
        if utils.is_excluded_path(request.path) or utils.is_bot(request.META.get('HTTP_USER_AGENT', '')):
            return
        meta = {'method': 'POST'} if request.method == 'POST' else {}
        tracking.record(
            Event.Type.REQUEST, path=request.path, status_code=response.status_code, duration_ms=duration_ms,
            meta=meta, visitor=visitor,
        )

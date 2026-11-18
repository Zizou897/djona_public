"""Mesure chaque requête (statut, durée) et repère les actions de navigation utiles (recherches, fiches).

Doit rester le premier middleware : il mesure alors toute la pile. Toute erreur de suivi est avalée — le site
ne doit jamais échouer ni ralentir à cause de ses statistiques.
"""
import logging
import time

from . import tracking, utils
from .models import Event

logger = logging.getLogger(__name__)

# Paramètres de recherche conservés (liste fermée : jamais de paramètre inconnu).
VEHICLE_SEARCH_PARAMS = ('brand', 'type', 'city', 'fuel_type', 'transmission', 'condition', 'price_min', 'price_max')
PART_SEARCH_PARAMS = ('q', 'categorie', 'marque', 'modele', 'annee', 'budget')


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
        path = request.path
        if utils.is_excluded_path(path) or utils.is_bot(request.META.get('HTTP_USER_AGENT', '')):
            return

        meta = {'method': 'POST'} if request.method == 'POST' else {}
        tracking.record(
            Event.Type.REQUEST, path=path, status_code=response.status_code, duration_ms=duration_ms,
            meta=meta, visitor=visitor,
        )
        self._record_navigation_action(request, response, visitor)

    def _record_navigation_action(self, request, response, visitor):
        match = getattr(request, 'resolver_match', None)
        view_name = match.view_name if match else ''
        ok = response.status_code < 400

        if request.method == 'GET' and ok and view_name == 'catalog:list':
            params = self._search_meta(request, VEHICLE_SEARCH_PARAMS)
            if params:
                tracking.record(Event.Type.ACTION, name='recherche_vehicule', path=request.path, meta=params, visitor=visitor)
        elif request.method == 'GET' and ok and view_name == 'parts:search':
            params = self._search_meta(request, PART_SEARCH_PARAMS)
            if params:
                tracking.record(Event.Type.ACTION, name='recherche_piece', path=request.path, meta=params, visitor=visitor)
        elif request.method == 'GET' and response.status_code == 200 and view_name == 'catalog:detail':
            tracking.record(Event.Type.ACTION, name='vehicule_vu', path=request.path,
                            meta={'slug': match.kwargs.get('slug', '')}, visitor=visitor)
        elif request.method == 'GET' and response.status_code == 200 and view_name == 'parts:detail':
            tracking.record(Event.Type.ACTION, name='piece_vue', path=request.path,
                            meta={'piece': match.kwargs.get('pk', '')}, visitor=visitor)
        elif request.method == 'POST' and ok and view_name == 'parts:cart_add':
            tracking.record(Event.Type.ACTION, name='panier_ajout', path=request.path,
                            meta={'piece': match.kwargs.get('pk', '')}, visitor=visitor)

    @staticmethod
    def _search_meta(request, allowed):
        meta = {}
        for key in allowed:
            values = [v.strip() for v in request.GET.getlist(key) if v.strip()]
            if values:
                meta[key] = ','.join(values)[:utils.MAX_META_VALUE_LENGTH]
        return meta

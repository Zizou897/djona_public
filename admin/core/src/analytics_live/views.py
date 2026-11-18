import logging

from django.http import Http404, JsonResponse
from django.views import View
from django.views.generic import TemplateView

from app.views import StaffRequisMixin

from . import stats
from .models import SITES

logger = logging.getLogger(__name__)


def _site_or_404(request):
    site = request.GET.get('site', 'public')
    if site not in SITES:
        raise Http404('Site inconnu')
    return site


class LiveDashboardView(StaffRequisMixin, TemplateView):
    """Page « Temps réel » : le contenu est chargé par le navigateur (interrogation toutes les 5 s)."""

    template_name = 'analytics_live/live.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site'] = _site_or_404(self.request)
        context['sites'] = [{'key': key, 'label': value['label']} for key, value in SITES.items()]
        return context


class LiveStatsView(StaffRequisMixin, View):
    def get(self, request):
        site = _site_or_404(request)
        try:
            return JsonResponse(stats.snapshot(site))
        except Exception:
            # Base du site injoignable, ou tables pas encore créées (migration du site non déployée).
            logger.warning('Temps réel : statistiques indisponibles pour %s', site, exc_info=True)
            return JsonResponse({'unavailable': True}, status=503)


class LiveEventsView(StaffRequisMixin, View):
    def get(self, request):
        site = _site_or_404(request)
        since = request.GET.get('since', '0')
        try:
            items = stats.feed(site, since=int(since) if since.isdigit() else 0)
        except Exception:
            logger.warning('Temps réel : flux indisponible pour %s', site, exc_info=True)
            return JsonResponse({'unavailable': True}, status=503)
        return JsonResponse({'events': items})

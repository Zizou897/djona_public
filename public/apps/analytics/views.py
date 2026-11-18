"""Point de collecte du script de suivi (`static/js/analytics.js`)."""
import hmac
import json

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.throttle import compter

from . import tracking, utils
from .models import Event

MAX_BODY_BYTES = 2048
RATE_WINDOW = 60       # secondes
RATE_LIMIT = 120       # requêtes de collecte par IP et par fenêtre (un heartbeat toutes les 15 s = 4/min)
ALLOWED_TYPES = {'pageview', 'heartbeat', 'action'}


@csrf_exempt
@require_POST
def collect(request):
    """Reçoit `{k, sid, t, p, n, m}` : clé du site, session anonyme, type, chemin, nom d'action, métadonnées.

    Répond toujours 204 quand l'événement est ignoré pour une raison bénigne (robot, type inconnu) : le script
    n'a rien à corriger. La clé de site n'est pas un secret (elle est dans la page) : elle écarte seulement le bruit.
    """
    if not tracking.enabled():
        raise Http404
    if len(request.body) > MAX_BODY_BYTES:
        return HttpResponse(status=413)
    try:
        body = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    key = body.get('k')
    if not isinstance(key, str) or not hmac.compare_digest(key.encode(), settings.ANALYTICS_SITE_KEY.encode()):
        return HttpResponse(status=403)

    ip = utils.client_ip(request)
    if compter(f'analytics-collect:{ip}', RATE_WINDOW) > RATE_LIMIT:
        return HttpResponse(status=429)

    user_agent = request.META.get('HTTP_USER_AGENT', '')
    kind = body.get('t')
    session_id = utils.valid_session_id(body.get('sid'))
    path = body.get('p')
    if utils.is_bot(user_agent) or kind not in ALLOWED_TYPES or not session_id:
        return HttpResponse(status=204)
    if not isinstance(path, str) or not path.startswith('/') or utils.is_excluded_path(utils.clean_path(path)):
        return HttpResponse(status=204)

    visitor = {
        'session_id': session_id,
        'device': utils.device_from_user_agent(user_agent),
        'country': utils.country_from_request(request),
        'ip_anon': utils.anonymize_ip(ip),
    }
    tracking.touch_presence(session_id, path, visitor['device'])

    if kind == 'pageview':
        tracking.record(Event.Type.PAGEVIEW, path=path, visitor=visitor, meta={'ref': _referrer_host(body.get('r'))})
    elif kind == 'action':
        name = body.get('n')
        if isinstance(name, str) and utils.EVENT_NAME_RE.match(name):
            tracking.record(Event.Type.ACTION, name=name, path=path, visitor=visitor, meta=body.get('m'))
    return HttpResponse(status=204)


def _referrer_host(value):
    """Seul le nom d'hôte du site référent est conservé (jamais l'URL complète)."""
    if not isinstance(value, str) or not value:
        return ''
    host = value.split('://', 1)[-1].split('/', 1)[0].split('?', 1)[0]
    return host[:80] if host and '.' in host else ''

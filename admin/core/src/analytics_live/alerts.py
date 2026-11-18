"""Alertes : détection (pic d'erreurs 5xx, lenteur, chute de trafic, site inaccessible) et envoi (e-mail, Telegram).

Principes :
  - les seuils viennent des réglages (`ALERT_*`, donc du .env), jamais du code ;
  - rien n'est envoyé tant qu'aucun canal n'est configuré (ALERT_EMAILS, TELEGRAM_*) ;
  - anti-spam : un incident n'est signalé qu'une fois, puis rappelé au plus toutes les ALERT_COOLDOWN_MINUTES ;
  - un message « résolu » part quand la situation redevient normale.
"""
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from . import stats
from .models import AlertState, SITES

logger = logging.getLogger(__name__)

HEALTH_TIMEOUT = 10
TELEGRAM_TIMEOUT = 10
ERRORS_WINDOW = timedelta(minutes=5)
SLOW_WINDOW = timedelta(minutes=10)
TRAFFIC_WINDOW = timedelta(minutes=15)
TRAFFIC_BASELINE_WINDOW = timedelta(minutes=60)


@dataclass
class Condition:
    key: str          # type d'alerte, ex. « erreurs_5xx »
    problem: bool
    title: str        # sujet quand l'incident démarre
    detail: str       # précision chiffrée
    counts_failures: bool = False  # ping de santé : le problème doit durer plusieurs vérifications


# --- Détection -------------------------------------------------------------------------------------------

def check_errors(alias, now):
    health = stats.request_health(alias, window=ERRORS_WINDOW, now=now)
    count = health['errors_5xx']
    limit = settings.ALERT_5XX_MIN_COUNT
    return Condition(
        'erreurs_5xx', count >= limit, 'Pic d\'erreurs serveur (5xx)',
        f'{count} erreur(s) 5xx sur {health["total"]} requêtes en 5 minutes (seuil : {limit}).',
    )


def check_slowness(alias, now):
    health = stats.request_health(alias, window=SLOW_WINDOW, now=now)
    limit = settings.ALERT_SLOW_P95_MS
    slow = health['total'] >= settings.ALERT_MIN_REQUESTS and health['p95_ms'] >= limit
    return Condition(
        'lenteur', slow, 'Temps de réponse anormal',
        f'p95 à {health["p95_ms"]} ms sur {health["total"]} requêtes en 10 minutes (seuil : {limit} ms).',
    )


def check_traffic(alias, now):
    recent = stats.count_pageviews(alias, now - TRAFFIC_WINDOW, now)
    window = TRAFFIC_BASELINE_WINDOW
    before = stats.count_pageviews(alias, now - TRAFFIC_WINDOW - window, now - TRAFFIC_WINDOW)
    baseline = before * TRAFFIC_WINDOW / window   # pages vues attendues sur 15 minutes
    drop = settings.ALERT_TRAFFIC_DROP_PCT
    dropped = baseline >= settings.ALERT_TRAFFIC_MIN_BASELINE and recent <= baseline * (100 - drop) / 100
    return Condition(
        'chute_trafic', dropped, 'Chute brutale du trafic',
        f'{recent} page(s) vue(s) sur 15 minutes contre ~{round(baseline)} attendues (baisse d\'au moins {drop} %).',
    )


def ping(url):
    """Renvoie (ok, détail). Un statut 5xx, un refus de connexion ou un délai dépassé = site inaccessible."""
    request = urllib.request.Request(url, headers={'User-Agent': 'DjonaHealthCheck/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=HEALTH_TIMEOUT) as response:
            return response.status < 500, f'HTTP {response.status}'
    except urllib.error.HTTPError as error:
        return error.code < 500, f'HTTP {error.code}'
    except Exception as error:
        return False, f'{type(error).__name__}: {error}'[:200]


def check_health(site):
    url = settings.ALERT_HEALTH_URLS.get(site)
    if not url:
        return None
    ok, detail = ping(url)
    return Condition('site_inaccessible', not ok, 'Site inaccessible', f'{url} → {detail}', counts_failures=True)


def evaluate(site, now):
    """Toutes les conditions d'un site ; une vérification qui échoue (tables absentes…) est ignorée, pas fatale."""
    alias = stats.alias_for(site)
    conditions = []
    try:
        conditions += [check(alias, now) for check in (check_errors, check_slowness, check_traffic)]
    except Exception:
        # Tables absentes (suivi pas encore déployé sur ce site) ou base injoignable : pas d'alerte statistique.
        logger.warning('Alertes : statistiques indisponibles pour %s', site, exc_info=True)
    health = check_health(site)
    if health:
        conditions.append(health)
    return conditions


# --- Envoi -----------------------------------------------------------------------------------------------

def channels():
    names = []
    if settings.ALERT_EMAILS:
        names.append('e-mail')
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        names.append('telegram')
    return names


def _send_telegram(text):
    url = f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = json.dumps({'chat_id': settings.TELEGRAM_CHAT_ID, 'text': text, 'disable_web_page_preview': True}).encode()
    request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=TELEGRAM_TIMEOUT):
        pass


def notify(subject, body):
    """Envoie sur chaque canal configuré (un canal en panne n'empêche pas les autres). Renvoie les canaux réussis."""
    sent = []
    if settings.ALERT_EMAILS:
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, settings.ALERT_EMAILS, fail_silently=False)
            sent.append('e-mail')
        except Exception:
            logger.exception('Alertes : envoi e-mail impossible')
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        try:
            _send_telegram(f'{subject}\n\n{body}')
            sent.append('telegram')
        except Exception:
            # L'URL de l'API contient le jeton du bot : on ne journalise jamais l'exception brute.
            logger.error('Alertes : envoi Telegram impossible')
    if not sent and not channels():
        logger.info('Alertes : aucun canal configuré, message non envoyé — %s', subject)
    return sent


# --- Machine d'états (anti-spam, résolution) --------------------------------------------------------------

def process(site, condition, now, dry_run=False):
    """Fait avancer l'état de l'alerte et envoie le message utile. Renvoie l'action : 'ouverte', 'rappel', 'resolue' ou ''."""
    key = f'{site}:{condition.key}'
    state = AlertState.objects.filter(key=key).first() or AlertState(key=key)
    label = SITES[site]['label']
    cooldown = timedelta(minutes=settings.ALERT_COOLDOWN_MINUTES)
    action = ''

    if condition.problem:
        state.failures += 1
        state.detail = condition.detail[:255]
        confirmed = not condition.counts_failures or state.failures >= settings.ALERT_HEALTH_FAILURES
        if confirmed and not state.active:
            state.active, state.since, action = True, now, 'ouverte'
        elif confirmed and state.active and (state.last_sent_at is None or now - state.last_sent_at >= cooldown):
            action = 'rappel'
        if action and not dry_run:
            notify(f'[Djona] {label} — {condition.title}', f'{condition.detail}\n\nIncident démarré à {timezone.localtime(state.since):%H:%M} ({label}).')
            state.last_sent_at = now
    else:
        state.failures = 0
        if state.active:
            action = 'resolue'
            if not dry_run:
                notify(f'[Djona] {label} — rétabli : {condition.title}', f'La situation est redevenue normale ({label}).\nIncident ouvert depuis {timezone.localtime(state.since):%H:%M}.')
            state.active, state.since, state.last_sent_at, state.detail = False, None, None, ''

    if not dry_run:
        state.updated_at = now
        state.save()
    return action


def run(now=None, dry_run=False, sites=None):
    """Évalue tous les sites. Renvoie la liste (site, condition, action) pour l'affichage de la commande."""
    now = now or timezone.now()
    results = []
    for site in sites or SITES:
        for condition in evaluate(site, now):
            results.append((site, condition, process(site, condition, now, dry_run=dry_run)))
    return results

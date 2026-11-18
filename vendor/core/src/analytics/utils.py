"""Fonctions pures du suivi : anonymisation, appareil, robots, nettoyage des métadonnées."""
import ipaddress
import re

# Robots d'indexation, outils de supervision et clients scriptés : exclus du trafic mesuré.
BOT_RE = re.compile(
    r'bot|crawl|spider|slurp|facebookexternalhit|bingpreview|headless|lighthouse|pingdom|uptime|monitor|'
    r'healthcheck|curl/|wget|python-requests|python-urllib|go-http-client|httpclient|axios|node-fetch',
    re.IGNORECASE,
)

SESSION_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,40}$')
EVENT_NAME_RE = re.compile(r'^[a-z0-9_.-]{1,60}$')

# Chemins jamais suivis : fichiers statiques, médias, administration Django, le point de collecte lui-même.
EXCLUDED_PREFIXES = ('/static/', '/media/', '/admin/', '/analytics/', '/.well-known/')
EXCLUDED_PATHS = {'/favicon.ico', '/robots.txt', '/sitemap.xml'}

# Une métadonnée dont le nom évoque une donnée personnelle n'est jamais conservée.
SENSITIVE_KEY_RE = re.compile(r'pass|pwd|token|secret|card|cvv|iban|phone|tel|mail|nom|name|adresse|address', re.IGNORECASE)
MAX_META_KEYS = 10
MAX_META_VALUE_LENGTH = 100


def is_bot(user_agent):
    return not user_agent or bool(BOT_RE.search(user_agent))


def is_excluded_path(path):
    return path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PREFIXES)


def device_from_user_agent(user_agent):
    ua = (user_agent or '').lower()
    if 'ipad' in ua or 'tablet' in ua or ('android' in ua and 'mobile' not in ua):
        return 'tablet'
    if 'mobi' in ua or 'iphone' in ua or 'android' in ua:
        return 'mobile'
    return 'desktop'


def anonymize_ip(ip):
    """IPv4 : dernier octet remis à 0 ; IPv6 : réduite au préfixe /48. Valeur illisible → chaîne vide."""
    try:
        address = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return ''
    if address.version == 4:
        return str(ipaddress.ip_network(f'{address}/24', strict=False).network_address)
    return str(ipaddress.ip_network(f'{address}/48', strict=False).network_address) + '/48'


def client_ip(request):
    # X-Real-IP est posé par nginx (il écrase la valeur envoyée par le client) ; REMOTE_ADDR en local.
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or ''


def country_from_request(request):
    """Pays fourni par un proxy (Cloudflare : CF-IPCountry). Sans base GeoIP, vide sinon."""
    code = (request.META.get('HTTP_CF_IPCOUNTRY') or '').strip().upper()
    return code if len(code) == 2 and code.isalpha() and code != 'XX' else ''


def valid_session_id(value):
    return value if isinstance(value, str) and SESSION_ID_RE.match(value) else ''


def clean_meta(meta):
    """Garde au plus MAX_META_KEYS valeurs simples, tronquées, sans clé évoquant une donnée personnelle."""
    if not isinstance(meta, dict):
        return {}
    cleaned = {}
    for key, value in meta.items():
        if len(cleaned) >= MAX_META_KEYS:
            break
        if not isinstance(key, str) or not re.match(r'^[A-Za-z0-9_.-]{1,40}$', key) or SENSITIVE_KEY_RE.search(key):
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = value[:MAX_META_VALUE_LENGTH]
    return cleaned


def clean_path(path):
    """Chemin sans paramètres de requête ni ancre, borné à 255 caractères."""
    return (path or '').split('?', 1)[0].split('#', 1)[0][:255]

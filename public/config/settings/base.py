"""
Réglages communs à tous les environnements.
Voir AGENTS.md §4 et §6 pour l'architecture cible et le design system.
"""
from pathlib import Path
from decouple import config

# BASE_DIR pointe sur la racine du dépôt (djona_public/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='change-me-in-production')

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'django_htmx',
]

LOCAL_APPS = [
    'apps.core',
    'apps.catalog',
    'apps.vendor_sync',
    'apps.parts',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.active_partners',
                'apps.core.context_processors.site_contact',
                'apps.core.context_processors.parts_cart',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Localisation — interface en français, marché Côte d'Ivoire (AGENTS.md §7)
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'static_cdn'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media_cdn'

# Doit rester alignée avec client_max_body_size (nginx) — sinon un fichier
# accepté par nginx peut quand même être rejeté par Django avant nginx.
DATA_UPLOAD_MAX_MEMORY_SIZE = 4 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 4 * 1024 * 1024

# Cache basé fichiers plutôt que LocMemCache (par défaut) : LocMemCache est
# propre à chaque processus, donc un rate-limit ne serait pas partagé entre les
# workers gunicorn en prod. FileBasedCache est partagé (simples fichiers sur
# disque) sans dépendance supplémentaire (Redis/Memcached).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': BASE_DIR / 'cache_framework',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Destinataires des notifications email de nouvelle demande de transport
# (équipe Djona, contact transport du partenaire). Vide = pas d'email.
from decouple import config as _config  # noqa: E402

TRANSPORT_NOTIFY_EMAILS = [e.strip() for e in _config('TRANSPORT_NOTIFY_EMAILS', default='').split(',') if e.strip()]

# URLs absolues utilisées dans les e-mails (logo, boutons) — le front et le back-office.
SITE_URL = _config('SITE_URL', default='https://djona.tech').rstrip('/')
ADMIN_SITE_URL = _config('ADMIN_SITE_URL', default='https://admin.djona.tech').rstrip('/')

# Destinataires des notifications email de nouveau message de contact. Vide = pas d'email.
PARTS_NOTIFY_EMAILS = [e.strip() for e in _config('PARTS_NOTIFY_EMAILS', default='').split(',') if e.strip()]
CONTACT_NOTIFY_EMAILS = [e.strip() for e in _config('CONTACT_NOTIFY_EMAILS', default='').split(',') if e.strip()]

# E-mail — SMTP Brevo (relais smtp-relay.brevo.com), expéditeur sur le domaine djona.tech.
# EMAIL_HOST_USER = identifiant SMTP Brevo (ce n'est PAS l'adresse expéditrice) ; EMAIL_HOST_PASSWORD = clé SMTP Brevo.
# DEFAULT_FROM_EMAIL doit être un expéditeur validé dans Brevo (domaine djona.tech authentifié).
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = _config('EMAIL_HOST', default='') or 'smtp-relay.brevo.com'
EMAIL_HOST_USER = _config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = _config('EMAIL_HOST_PASSWORD', default='')
EMAIL_PORT = _config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = _config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_TIMEOUT = _config('EMAIL_TIMEOUT', default=10, cast=int)  # sans délai, un SMTP lent bloquerait un worker
DEFAULT_FROM_EMAIL = _config('DEFAULT_FROM_EMAIL', default='') or 'Djona <noreply@djona.tech>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Envoi par l'API Brevo (HTTPS, sans SMTP) : prioritaire sur le SMTP dès que BREVO_API_KEY est défini.
# L'expéditeur reste soumis à validation dans Brevo ; l'IP du serveur doit être autorisée (Sécurité > Adresses IP autorisées).
BREVO_API_KEY = _config('BREVO_API_KEY', default='')
if BREVO_API_KEY:
    EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
    ANYMAIL = {'BREVO_API_KEY': BREVO_API_KEY, 'REQUESTS_TIMEOUT': (5, 15)}

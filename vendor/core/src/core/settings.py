import sys
from pathlib import Path

from decouple import Config, RepositoryEmpty, RepositoryEnv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# decouple's default `config` searches upward through parent directories for
# a .env file, with no boundary — on a dev machine with multiple projects,
# this can silently pick up an unrelated project's .env (and its database
# credentials). Scope the search strictly to this project's own directory
# (core/.env, next to .env.example — one level above BASE_DIR/src).
_env_file = BASE_DIR.parent / '.env'
if _env_file.is_file():
    config = Config(RepositoryEnv(str(_env_file)))
else:
    config = Config(RepositoryEmpty())

# Réglages « fermés par défaut » : sans .env, le projet ne doit pas démarrer en mode debug,
# avec une clé publique ni accepter n'importe quel nom d'hôte. En développement, DEBUG=True est
# posé explicitement dans .env (voir .env.example).
SECRET_KEY = config('SECRET_KEY', default='')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='localhost,127.0.0.1,[::1]').split(',') if h.strip()]

# Valeurs connues et publiques (placeholder de .env.example, ancienne valeur par défaut) : refusées hors debug,
# sinon les sessions et les liens de réinitialisation de mot de passe seraient falsifiables.
_CLES_PUBLIQUES = {'', 'change-me-in-production', 'your-secret-key-here'}
if not DEBUG and SECRET_KEY in _CLES_PUBLIQUES:
    raise ImproperlyConfigured("SECRET_KEY manquante ou factice : définissez une clé secrète unique dans .env (DEBUG=False).")
if DEBUG and not SECRET_KEY:
    SECRET_KEY = 'dev-only-insecure-key'

DJANGO_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'tinymce',
    'colorfield',
    'corsheaders',
    'sweetify',
    'after_response',
]

LOCAL_APPS = [
    'app',
    'annonces',
    'pro',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

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
                'app.context_processors.espace_vendeur',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Base de données — switcher via .env
if config('USE_MYSQL', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('MYSQL_DB'),
            'USER': config('MYSQL_USER'),
            'PASSWORD': config('MYSQL_PASSWORD'),
            'HOST': config('MYSQL_HOST', default='localhost'),
            'PORT': config('MYSQL_PORT', default='3306'),
        }
    }

    # MYSQL_SSL_REQUIRED=True si MySQL est un service managé distant exigeant TLS
    # (ex. Aiven). Un MySQL local (VPS ou poste de dev) n'a pas de certificat
    # configuré par défaut — laisser à False dans ce cas (valeur par défaut).
    if config('MYSQL_SSL_REQUIRED', default=False, cast=bool):
        DATABASES['default']['OPTIONS'] = {'ssl': {'ssl-mode': 'REQUIRED'}}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'app.Utilisateur'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'app.validators.ComplexiteMotDePasseValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOGIN_URL = 'connexion_vendeur'
LOGIN_REDIRECT_URL = 'tableau_de_bord_vendeur'
LOGOUT_REDIRECT_URL = 'connexion_vendeur'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'static_cdn'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media_cdn'

# Taille TOTALE de requête max (formulaire d'annonce : jusqu'à 4 photos de 4 Mo
# chacune, voir annonces/forms.py::MAX_PHOTOS/MAX_PHOTO_SIZE, + marge pour les
# autres champs et l'overhead multipart). La limite PAR image (4 Mo) est
# appliquée séparément dans AnnonceForm.clean() — ces réglages-ci ne font que
# laisser passer la requête jusqu'à Django pour que cette validation s'exécute ;
# ils ne remplacent pas le contrôle par fichier. Doit rester alignée avec
# client_max_body_size (nginx, site vendor.djona.tech) — sinon nginx rejette
# la requête avant même que Django ne la voie.
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cache fichiers, partagé entre les workers gunicorn (LocMemCache est propre à chaque processus : la limitation
# des tentatives de connexion y serait multipliée par le nombre de workers et perdue à chaque redémarrage).
# Le dossier doit appartenir à l'utilisateur de gunicorn : voir deploy/deploy_*.sh. Pendant les tests, cache
# en mémoire pour ne pas garder de compteurs d'une exécution à l'autre.
if 'test' in sys.argv[1:2]:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache', 'LOCATION': BASE_DIR / 'cache_framework'}}

# E-mail — SMTP Brevo (relais smtp-relay.brevo.com), expéditeur sur le domaine djona.tech.
# EMAIL_HOST_USER = identifiant SMTP Brevo (ce n'est PAS l'adresse expéditrice) ; EMAIL_HOST_PASSWORD = clé SMTP Brevo.
# DEFAULT_FROM_EMAIL doit être un expéditeur validé dans Brevo (domaine djona.tech authentifié).
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='') or 'smtp-relay.brevo.com'
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)  # sans délai, un SMTP lent bloquerait un worker
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='') or 'Djona <noreply@djona.tech>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Envoi par l'API Brevo (HTTPS, sans SMTP) : prioritaire sur le SMTP dès que BREVO_API_KEY est défini.
# L'expéditeur reste soumis à validation dans Brevo ; l'IP du serveur doit être autorisée (Sécurité > Adresses IP autorisées).
BREVO_API_KEY = config('BREVO_API_KEY', default='')
if BREVO_API_KEY:
    EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
    ANYMAIL = {'BREVO_API_KEY': BREVO_API_KEY, 'REQUESTS_TIMEOUT': (5, 15)}
if DEBUG and not (EMAIL_HOST_USER or BREVO_API_KEY):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # développement : e-mails affichés dans la console

# Mot de passe oublié : validité du lien (secondes) et domaine utilisé dans les e-mails.
# PASSWORD_RESET_DOMAIN (ex. vendor.djona.tech) évite que le lien soit construit à partir de l'en-tête
# Host de la requête ; à défaut, l'hôte de la requête est utilisé (développement).
PASSWORD_RESET_TIMEOUT = 60 * 60
PASSWORD_RESET_DOMAIN = config('PASSWORD_RESET_DOMAIN', default='')

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://127.0.0.1:6379')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://127.0.0.1:6379')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Déclenchement de la synchro marketplace quand une annonce publiée est modifiée
# ou supprimée par son vendeur (elle doit disparaître/se dépublier du catalogue
# public sans attendre la prochaine validation admin) — voir annonces/sync.py.
# Laisser vide en dev si le projet public n'est pas installé localement : le
# déclenchement est alors simplement ignoré (loggé), pas d'erreur.
PUBLIC_SYNC_PYTHON = config('PUBLIC_SYNC_PYTHON', default='')
PUBLIC_SYNC_MANAGE_PY = config('PUBLIC_SYNC_MANAGE_PY', default='')
PUBLIC_SYNC_SETTINGS = config('PUBLIC_SYNC_SETTINGS', default='config.settings.prod')

# Jazzmin
JAZZMIN_SETTINGS = {
    'site_title': 'Djona Vendeur',
    'site_header': 'Djona Vendeur',
    'site_brand': 'Djona Vendeur',
    'show_ui_builder': False,
}
JAZZMIN_UI_TWEAKS = {'theme': 'cyborg'}

# Sécurité production
if not DEBUG:
    # nginx termine le TLS et transmet en HTTP : sans cet en-tête, Django croirait chaque requête non sécurisée
    # (redirection HTTPS en boucle, cookies « Secure » jamais envoyés, HSTS jamais émis).
    # nginx doit poser `proxy_set_header X-Forwarded-Proto $scheme;` (comme pour le site public).
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)  # 1 an ; 0 pour désactiver

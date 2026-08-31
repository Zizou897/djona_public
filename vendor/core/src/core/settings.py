from pathlib import Path
from decouple import Config, RepositoryEmpty, RepositoryEnv

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

SECRET_KEY = config('SECRET_KEY', default='change-me-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

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
]

LOCAL_APPS = [
    'app',
    'annonces',
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

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://127.0.0.1:6379')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://127.0.0.1:6379')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

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
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

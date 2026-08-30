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
    'moderation',
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
        },
        # Connexion en lecture/écriture vers le schéma du projet vendor (comptes
        # vendeur + annonces). Même serveur/utilisateur MySQL que `default`, seul le
        # nom de la base change. Utilisée uniquement par l'app `moderation`, via
        # `.using('vendor_db')` — jamais comme alias par défaut d'un modèle.
        #
        # ATTENTION : TEST.NAME pointe vers une base de test DÉDIÉE
        # (djona_vendor_test), PAS vers la vraie base djona_vendor. Le test-runner
        # Django exécute un DROP DATABASE + CREATE DATABASE sur TEST.NAME à chaque
        # `manage.py test` (sauf --keepdb) — pointer ça vers la vraie base
        # détruirait les données réelles du projet vendor. djona_vendor_test est
        # peuplée en rejouant les migrations du projet vendor dessus (même
        # utilisateur MySQL, mêmes identifiants, juste un autre nom de base) ; à
        # refaire si les modèles vendor changent de schéma.
        'vendor_db': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('VENDOR_MYSQL_DB', default='djona_vendor'),
            'USER': config('MYSQL_USER'),
            'PASSWORD': config('MYSQL_PASSWORD'),
            'HOST': config('MYSQL_HOST', default='localhost'),
            'PORT': config('MYSQL_PORT', default='3306'),
            # DEPENDENCIES vide : vendor_db est une base indépendante, pas une
            # réplique de `default`. Sans ceci, Django exige implicitement que
            # `default` soit aussi préparée avant vendor_db ; or `manage.py test
            # moderation` ne référence que vendor_db, donc `default` n'est jamais
            # incluse dans les alias demandés et Django lève à tort
            # "Circular dependency in TEST[DEPENDENCIES]".
            'TEST': {
                'NAME': config('VENDOR_TEST_MYSQL_DB', default='djona_vendor_test'),
                'DEPENDENCIES': [],
            },
        },
    }

    # MYSQL_SSL_REQUIRED=True si MySQL est un service managé distant exigeant TLS
    # (ex. Aiven). Un MySQL local (VPS ou poste de dev) n'a pas de certificat
    # configuré par défaut — laisser à False dans ce cas (valeur par défaut).
    if config('MYSQL_SSL_REQUIRED', default=False, cast=bool):
        DATABASES['default']['OPTIONS'] = {'ssl': {'ssl-mode': 'REQUIRED'}}
        DATABASES['vendor_db']['OPTIONS'] = {'ssl': {'ssl-mode': 'REQUIRED'}}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Empêche toute migration (de n'importe quelle app) d'être appliquée sur
# vendor_db — ce schéma est possédé et migré exclusivement par le projet
# vendor. Voir core/db_routers.py pour le détail du problème que ça évite.
DATABASE_ROUTERS = ['core.db_routers.VendorDbRouter']

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

AUTHENTICATION_BACKENDS = [
    'app.backends.EmailOrUsernameBackend',
    'django.contrib.auth.backends.ModelBackend',
]
LOGIN_URL = 'connexion_admin'
LOGIN_REDIRECT_URL = 'dashboard_admin'
LOGOUT_REDIRECT_URL = 'connexion_admin'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'static_cdn'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media_cdn'
# Les photos d'annonces (AnnoncePhotoMirror, moderation/models.py) sont référencées via
# vendor_db mais les fichiers réels vivent sur le disque du projet vendor
# (vendor/core/src/media_cdn/annonces/), pas ici. media_cdn/annonces/ de ce projet doit
# être un lien vers celui de vendor — sans ça, les images d'annonce sont cassées (404)
# car ce MEDIA_ROOT ne contient pas les fichiers. Non versionné (comme media_cdn/
# lui-même) : à recréer après un clone frais ou un déploiement.
#   - Windows (dev local) : mklink /J media_cdn\annonces ..\..\..\vendor\core\src\media_cdn\annonces
#     (chemin relatif depuis admin/core/src)
#   - Linux (VPS de prod — admin et vendor partagent le même serveur) :
#     ln -s /chemin/absolu/vers/vendor/core/src/media_cdn/annonces media_cdn/annonces

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
    'site_title': 'Admin core',
    'site_header': 'core',
    'site_brand': 'core',
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

from decouple import config

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('MYSQL_DB'),
        'USER': config('MYSQL_USER'),
        'PASSWORD': config('MYSQL_PASSWORD'),
        'HOST': config('MYSQL_HOST', default='localhost'),
        'PORT': config('MYSQL_PORT', default='3306'),
    },
    # Connexion en lecture seule vers le schéma du projet vendor (annonces validées
    # par l'admin). Même serveur MySQL que `default`. Utilisée uniquement par
    # apps.vendor_sync, via `.using('vendor_db')` — jamais comme alias par défaut
    # d'un modèle.
    'vendor_db': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('VENDOR_MYSQL_DB', default='djona_vendor'),
        'USER': config('VENDOR_MYSQL_USER'),
        'PASSWORD': config('VENDOR_MYSQL_PASSWORD'),
        'HOST': config('MYSQL_HOST', default='localhost'),
        'PORT': config('MYSQL_PORT', default='3306'),
    },
}

# MYSQL_SSL_REQUIRED=True si MySQL est un service managé distant exigeant TLS
# (ex. Aiven). Un MySQL installé localement sur le VPS n'a pas de certificat
# configuré par défaut — laisser à False dans ce cas (valeur par défaut).
if config('MYSQL_SSL_REQUIRED', default=False, cast=bool):
    DATABASES['default']['OPTIONS'] = {'ssl': {'ssl-mode': 'REQUIRED'}}
    DATABASES['vendor_db']['OPTIONS'] = {'ssl': {'ssl-mode': 'REQUIRED'}}

# Empêche toute migration d'être appliquée sur `vendor_db` — ce schéma est possédé
# et migré exclusivement par le projet vendor. Voir config/db_routers.py.
DATABASE_ROUTERS = ['config.db_routers.VendorDbRouter']

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

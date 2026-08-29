from decouple import config

from .base import *  # noqa: F401,F403

DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('MYSQL_DB'),
        'USER': config('MYSQL_USER'),
        'PASSWORD': config('MYSQL_PASSWORD'),
        'HOST': config('MYSQL_HOST'),
        'PORT': config('MYSQL_PORT'),
    },
    # Connexion en lecture seule vers le schéma du projet vendor (annonces validées
    # par l'admin). Même serveur MySQL que `default`, utilisateur dédié restreint à
    # SELECT sur djona_vendor. Utilisée uniquement par apps.vendor_sync, via
    # `.using('vendor_db')` — jamais comme alias par défaut d'un modèle.
    'vendor_db': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('VENDOR_MYSQL_DB', default='djona_vendor'),
        'USER': config('VENDOR_MYSQL_USER'),
        'PASSWORD': config('VENDOR_MYSQL_PASSWORD'),
        'HOST': config('MYSQL_HOST'),
        'PORT': config('MYSQL_PORT'),
    },
}

# Empêche toute migration d'être appliquée sur `vendor_db` — ce schéma est possédé
# et migré exclusivement par le projet vendor. Voir config/db_routers.py.
DATABASE_ROUTERS = ['config.db_routers.VendorDbRouter']

INTERNAL_IPS = ['127.0.0.1']

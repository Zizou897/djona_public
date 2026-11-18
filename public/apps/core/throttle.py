"""Limitation des tentatives (connexion, inscription) — protège contre le brute-force.

Les compteurs vivent dans le cache Django (fichiers, partagé entre les workers gunicorn : voir CACHES).
Chaque compteur est une fenêtre FIXE qui démarre à la première tentative : on stocke (nombre, échéance)
et on ré-écrit la clé avec le temps restant. On n'utilise pas cache.incr(), qui, sur le cache fichiers,
repart au délai par défaut (5 min) au lieu de conserver l'échéance d'origine.

Si le cache est indisponible (droits du dossier, disque plein…), la limitation est ignorée et l'erreur
journalisée : mieux vaut laisser se connecter que de renvoyer une 500 à tous les vendeurs.
"""
import hashlib
import logging
import time

from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

LOGIN_WINDOW = 15 * 60
LOGIN_LIMIT_PER_ACCOUNT = 5   # échecs par (IP, identifiant) — un attaquant ne bloque pas le vrai titulaire depuis une autre IP
LOGIN_LIMIT_PER_IP = 20       # échecs, tous identifiants confondus, par IP

SIGNUP_WINDOW = 60 * 60
SIGNUP_LIMIT_PER_IP = 10      # comptes créés par IP et par heure

MESSAGE_TROP_DE_TENTATIVES = 'Trop de tentatives de connexion. Réessayez dans {minutes} minutes.'


def client_ip(request):
    # X-Real-IP est posé par nginx (il écrase la valeur envoyée par le client) ; REMOTE_ADDR en local.
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or 'unknown'


def nombre(key):
    """Nombre de tentatives déjà comptées pour `key` dans la fenêtre en cours."""
    try:
        entry = cache.get(key)
    except Exception:
        logger.exception('Cache indisponible : limitation ignorée (%s)', key)
        return 0
    if not entry:
        return 0
    count, deadline = entry
    return count if deadline > time.time() else 0


def compter(key, window):
    """Ajoute une tentative à `key` (fenêtre fixe de `window` secondes) et renvoie le nouveau total."""
    try:
        now = time.time()
        entry = cache.get(key)
        if entry and entry[1] > now:
            count, deadline = entry[0] + 1, entry[1]
        else:
            count, deadline = 1, now + window
        cache.set(key, (count, deadline), max(int(deadline - now), 1))
        return count
    except Exception:
        logger.exception('Cache indisponible : limitation ignorée (%s)', key)
        return 0


def reinitialiser(key):
    try:
        cache.delete(key)
    except Exception:
        logger.exception('Cache indisponible (%s)', key)


class LoginThrottleMixin:
    """À placer devant AuthenticationForm : refuse d'authentifier au-delà des limites et compte les échecs."""

    def clean(self):
        request = self.request
        if request is None:
            return super().clean()
        ip = client_ip(request)
        identifiant = (self.cleaned_data.get('username') or '').strip().lower()
        cle_ip = f'login:ip:{ip}'
        cle_compte = f'login:compte:{ip}:{hashlib.sha256(identifiant.encode()).hexdigest()[:32]}'

        if nombre(cle_ip) >= LOGIN_LIMIT_PER_IP or (identifiant and nombre(cle_compte) >= LOGIN_LIMIT_PER_ACCOUNT):
            raise ValidationError(MESSAGE_TROP_DE_TENTATIVES.format(minutes=LOGIN_WINDOW // 60), code='throttled')
        try:
            cleaned = super().clean()
        except ValidationError:
            compter(cle_ip, LOGIN_WINDOW)
            if identifiant:
                compter(cle_compte, LOGIN_WINDOW)
            raise
        reinitialiser(cle_compte)
        return cleaned

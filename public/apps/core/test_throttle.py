from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from . import throttle

MOT_DE_PASSE = 'MotDePasse123!'


class LimitationConnexionAdminDjangoTests(TestCase):
    """Le /admin/ de Django du site public est limité contre le brute-force comme les autres projets."""

    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user(username='staff', password=MOT_DE_PASSE, is_staff=True)

    def tenter(self, mot_de_passe):
        return self.client.post(
            '/admin/login/', {'username': 'staff', 'password': mot_de_passe, 'next': '/admin/'}, HTTP_X_REAL_IP='10.0.0.1',
        )

    def test_bloque_apres_trop_d_echecs(self):
        for _ in range(throttle.LOGIN_LIMIT_PER_ACCOUNT):
            self.tenter('mauvais')
        self.assertContains(self.tenter(MOT_DE_PASSE), 'Trop de tentatives de connexion')

    def test_connexion_normale_possible(self):
        self.assertEqual(self.tenter(MOT_DE_PASSE).status_code, 302)

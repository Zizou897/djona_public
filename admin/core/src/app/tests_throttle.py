from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import throttle

User = get_user_model()
MOT_DE_PASSE = 'MotDePasse123!'
BLOQUE = 'Trop de tentatives de connexion'


class LimitationConnexionAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(username='staff', email='staff@exemple.ci', password=MOT_DE_PASSE, is_staff=True)

    def tenter(self, identifiant='staff', mot_de_passe='mauvais', ip='10.0.0.1', url=None):
        return self.client.post(
            url or reverse('connexion_admin'), {'username': identifiant, 'password': mot_de_passe, 'next': '/'},
            HTTP_X_REAL_IP=ip,
        )

    def test_le_bon_mot_de_passe_est_refuse_apres_trop_d_echecs(self):
        for _ in range(throttle.LOGIN_LIMIT_PER_ACCOUNT):
            self.tenter()
        self.assertContains(self.tenter(mot_de_passe=MOT_DE_PASSE), BLOQUE)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_sous_la_limite_la_connexion_reste_possible(self):
        for _ in range(throttle.LOGIN_LIMIT_PER_ACCOUNT - 1):
            self.tenter()
        self.assertEqual(self.tenter(mot_de_passe=MOT_DE_PASSE).status_code, 302)

    def test_l_email_et_le_nom_d_utilisateur_partagent_le_meme_compteur_par_identifiant_saisi(self):
        # L'attaquant ne contourne pas la limite en changeant la casse de l'identifiant.
        for variante in ('staff', 'STAFF', 'Staff', 'sTaFf', 'staff '):
            self.tenter(identifiant=variante)
        self.assertContains(self.tenter(mot_de_passe=MOT_DE_PASSE), BLOQUE)

    def test_le_titulaire_n_est_pas_bloque_depuis_une_autre_ip(self):
        for _ in range(throttle.LOGIN_LIMIT_PER_ACCOUNT):
            self.tenter()
        self.assertEqual(self.tenter(mot_de_passe=MOT_DE_PASSE, ip='10.0.0.2').status_code, 302)

    def test_l_admin_django_est_limite_aussi(self):
        for _ in range(throttle.LOGIN_LIMIT_PER_ACCOUNT):
            self.tenter(url='/admin/login/')
        self.assertContains(self.tenter(mot_de_passe=MOT_DE_PASSE, url='/admin/login/'), BLOQUE)

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import throttle
from .models import Utilisateur

MOT_DE_PASSE = 'MotDePasse1'
BLOQUE = 'Trop de tentatives de connexion'


class LimitationConnexionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password=MOT_DE_PASSE, nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        Utilisateur.objects.create_user(
            email='awa@exemple.ci', password=MOT_DE_PASSE, nom='Traoré', prenom='Awa', telephone='0102030406',
        )

    def tenter(self, email='ange@exemple.ci', mot_de_passe='mauvais', ip='10.0.0.1'):
        return self.client.post(
            reverse('connexion_vendeur'), {'username': email, 'password': mot_de_passe}, HTTP_X_REAL_IP=ip,
        )

    def echouer(self, fois, **kwargs):
        for _ in range(fois):
            self.assertContains(self.tenter(**kwargs), 'Email ou mot de passe incorrect.')

    def test_le_bon_mot_de_passe_est_refuse_apres_trop_d_echecs(self):
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT)
        reponse = self.tenter(mot_de_passe=MOT_DE_PASSE)
        self.assertContains(reponse, BLOQUE)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_sous_la_limite_la_connexion_reste_possible(self):
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT - 1)
        self.assertRedirects(self.tenter(mot_de_passe=MOT_DE_PASSE), reverse('tableau_de_bord_vendeur'))

    def test_un_autre_compte_depuis_la_meme_ip_n_est_pas_bloque(self):
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT)
        self.assertRedirects(self.tenter(email='awa@exemple.ci', mot_de_passe=MOT_DE_PASSE), reverse('tableau_de_bord_vendeur'))

    def test_le_titulaire_n_est_pas_bloque_depuis_une_autre_ip(self):
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT)
        self.assertRedirects(self.tenter(mot_de_passe=MOT_DE_PASSE, ip='10.0.0.2'), reverse('tableau_de_bord_vendeur'))

    def test_une_connexion_reussie_remet_le_compteur_a_zero(self):
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT - 1)
        self.tenter(mot_de_passe=MOT_DE_PASSE)
        self.client.logout()
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT - 1)  # repart de zéro : pas de blocage

    def test_limite_par_ip_tous_identifiants_confondus(self):
        for i in range(throttle.LOGIN_LIMIT_PER_IP):
            self.tenter(email=f'inconnu{i}@exemple.ci')
        self.assertContains(self.tenter(mot_de_passe=MOT_DE_PASSE), BLOQUE)

    def test_le_blocage_expire_avec_la_fenetre(self):
        self.echouer(throttle.LOGIN_LIMIT_PER_ACCOUNT)
        futur = throttle.time.time() + throttle.LOGIN_WINDOW + 5
        with mock.patch.object(throttle.time, 'time', return_value=futur):
            self.assertRedirects(self.tenter(mot_de_passe=MOT_DE_PASSE), reverse('tableau_de_bord_vendeur'))

    def test_la_fenetre_ne_se_prolonge_pas_a_chaque_echec(self):
        t0 = throttle.time.time()
        with mock.patch.object(throttle.time, 'time', return_value=t0):
            self.echouer(2)
        with mock.patch.object(throttle.time, 'time', return_value=t0 + throttle.LOGIN_WINDOW - 60):
            self.echouer(2)
        with mock.patch.object(throttle.time, 'time', return_value=t0 + throttle.LOGIN_WINDOW + 1):
            self.echouer(1)  # nouvelle fenêtre : le compteur est reparti de 1

    def test_cache_indisponible_ne_bloque_pas_la_connexion(self):
        with mock.patch.object(throttle, 'cache') as faux_cache, self.assertLogs(throttle.logger, 'ERROR'):
            faux_cache.get.side_effect = OSError('permission refusée')
            faux_cache.set.side_effect = OSError('permission refusée')
            faux_cache.delete.side_effect = OSError('permission refusée')
            self.assertContains(self.tenter(), 'Email ou mot de passe incorrect.')
            self.assertRedirects(self.tenter(mot_de_passe=MOT_DE_PASSE), reverse('tableau_de_bord_vendeur'))

    def test_l_admin_django_est_limite_aussi(self):
        Utilisateur.objects.create_superuser(
            email='root@exemple.ci', password=MOT_DE_PASSE, nom='Root', prenom='Root', telephone='0102030407',
        )

        def admin(mot_de_passe):
            return self.client.post(
                '/admin/login/', {'username': 'root@exemple.ci', 'password': mot_de_passe, 'next': '/admin/'},
                HTTP_X_REAL_IP='10.0.0.9',
            )

        for _ in range(throttle.LOGIN_LIMIT_PER_ACCOUNT):
            admin('mauvais')
        self.assertContains(admin(MOT_DE_PASSE), BLOQUE)


class LimitationInscriptionTests(TestCase):
    def setUp(self):
        cache.clear()

    def inscrire(self, email, ip='10.0.0.1'):
        return self.client.post(reverse('inscription_vendeur'), {
            'nom': 'Koffi', 'prenom': 'Ange', 'email': email, 'telephone': '0102030405',
            'type_compte': Utilisateur.TypeCompte.PARTICULIER, 'password': MOT_DE_PASSE, 'consentement': True,
        }, HTTP_X_REAL_IP=ip)

    def test_trop_de_comptes_depuis_la_meme_ip_sont_refuses(self):
        for _ in range(throttle.SIGNUP_LIMIT_PER_IP):
            throttle.compter('signup:ip:10.0.0.1', throttle.SIGNUP_WINDOW)
        reponse = self.inscrire('nouveau@exemple.ci')
        self.assertContains(reponse, 'Trop de comptes créés')
        self.assertFalse(Utilisateur.objects.filter(email='nouveau@exemple.ci').exists())

    def test_une_autre_ip_peut_s_inscrire(self):
        for _ in range(throttle.SIGNUP_LIMIT_PER_IP):
            throttle.compter('signup:ip:10.0.0.1', throttle.SIGNUP_WINDOW)
        self.inscrire('nouveau@exemple.ci', ip='10.0.0.2')
        self.assertTrue(Utilisateur.objects.filter(email='nouveau@exemple.ci').exists())

    def test_une_inscription_reussie_est_comptee(self):
        self.inscrire('nouveau@exemple.ci')
        self.assertEqual(throttle.nombre('signup:ip:10.0.0.1'), 1)

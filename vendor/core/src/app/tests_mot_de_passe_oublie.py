import json
import re
from datetime import datetime, timedelta
from smtplib import SMTPException
from unittest import mock

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Utilisateur

EMAIL = 'ange@exemple.ci'
ANCIEN = 'AncienMdp1'
NOUVEAU = 'NouveauMdp42'


class ResetBase(TestCase):
    def setUp(self):
        cache.clear()  # les demandes sont limitées par adresse
        self.user = Utilisateur.objects.create_user(
            email=EMAIL, password=ANCIEN, nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )

    def demander(self, email=EMAIL, **extra):
        return self.client.post(reverse('mot_de_passe_oublie'), {'email': email}, **extra)

    def lien(self, message=None):
        message = message or mail.outbox[-1]
        match = re.search(r'https?://\S+/reinitialisation/[^/\s]+/[^/\s]+/', message.body)
        self.assertIsNotNone(match, message.body)
        return match.group(0)


class PagesTests(ResetBase):
    def test_login_page_links_to_the_reset_page(self):
        html = self.client.get(reverse('connexion_vendeur')).content.decode()
        self.assertIn(f'href="{reverse("mot_de_passe_oublie")}">Mot de passe oublié', html)

    def test_pages_render(self):
        response = self.client.get(reverse('mot_de_passe_oublie'))
        self.assertContains(response, 'Mot de passe oublié ?')
        self.assertContains(response, 'name="email"')
        self.assertContains(self.client.get(reverse('mot_de_passe_oublie_envoye')), 'Vérifiez votre boîte mail')
        self.assertContains(self.client.get(reverse('mot_de_passe_reinitialise')), 'Mot de passe modifié')

    def test_validity_shown_comes_from_the_setting(self):
        self.assertContains(self.client.get(reverse('mot_de_passe_oublie_envoye')), 'valable 1 heure')
        with override_settings(PASSWORD_RESET_TIMEOUT=30 * 60):
            self.assertContains(self.client.get(reverse('mot_de_passe_oublie_envoye')), 'valable 30 minutes')
        with override_settings(PASSWORD_RESET_TIMEOUT=2 * 3600):
            self.assertContains(self.client.get(reverse('mot_de_passe_oublie_envoye')), 'valable 2 heures')


class RequestTests(ResetBase):
    def test_known_account_receives_the_link(self):
        response = self.demander()
        self.assertRedirects(response, reverse('mot_de_passe_oublie_envoye'))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [EMAIL])
        self.assertIn('Réinitialisation', message.subject)
        self.assertNotIn('\n', message.subject)
        self.assertIn('Ange', message.body)
        self.assertIn('valable 1 heure', message.body)
        self.assertTrue(message.alternatives, 'version HTML attendue')
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn(self.lien(), html)

    @override_settings(DEFAULT_FROM_EMAIL='Djona <noreply@djona.tech>', EMAIL_HOST_USER='identifiant-smtp@smtp-brevo.com')
    def test_sender_is_the_configured_address_not_the_smtp_login(self):
        self.demander()
        self.assertEqual(mail.outbox[0].from_email, 'Djona <noreply@djona.tech>')

    def test_email_is_matched_case_insensitively(self):
        self.demander(email='ANGE@Exemple.CI')
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_account_gets_the_same_response_and_no_mail(self):
        known = self.demander()
        mail.outbox.clear()
        unknown = self.demander(email='personne@exemple.ci')
        self.assertEqual((unknown.status_code, unknown.url), (known.status_code, known.url))
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_account_gets_no_mail(self):
        Utilisateur.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertRedirects(self.demander(), reverse('mot_de_passe_oublie_envoye'))
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email_is_refused(self):
        response = self.demander(email='pas-un-email')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'adresse email valide')
        self.assertEqual(len(mail.outbox), 0)

    def test_requests_are_limited_per_address_with_an_identical_response(self):
        responses = [self.demander() for _ in range(5)]
        self.assertEqual(len(mail.outbox), 3)  # 3 par heure et par adresse
        for response in responses:
            self.assertRedirects(response, reverse('mot_de_passe_oublie_envoye'), fetch_redirect_response=False)

    def test_smtp_failure_is_swallowed_and_logged(self):
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=SMTPException('boom')):
            with self.assertLogs('django.contrib.auth', level='ERROR'):
                response = self.demander()
        self.assertRedirects(response, reverse('mot_de_passe_oublie_envoye'))

    @override_settings(PASSWORD_RESET_DOMAIN='vendor.example.test', ALLOWED_HOSTS=['*'])
    def test_link_uses_the_configured_domain_not_the_host_header(self):
        self.demander(HTTP_HOST='evil.example')
        self.assertIn('vendor.example.test/reinitialisation/', mail.outbox[0].body)
        self.assertNotIn('evil.example', mail.outbox[0].body)
        self.assertNotIn('evil.example', mail.outbox[0].alternatives[0][0])


class ResetFlowTests(ResetBase):
    def ouvrir(self, lien, client=None):
        """Suit le lien de l'e-mail (redirection vers .../set-password/) et renvoie l'URL du formulaire."""
        response = (client or self.client).get(lien)
        self.assertEqual(response.status_code, 302)
        return response.url

    def choisir(self, url, mdp1=NOUVEAU, mdp2=None, client=None):
        return (client or self.client).post(url, {'new_password1': mdp1, 'new_password2': mdp2 or mdp1})

    def test_full_flow_changes_the_password(self):
        self.demander()
        url = self.ouvrir(self.lien())
        form = self.client.get(url)
        self.assertContains(form, 'Nouveau mot de passe')
        self.assertContains(form, 'name="new_password1"')
        self.assertRedirects(self.choisir(url), reverse('mot_de_passe_reinitialise'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NOUVEAU))
        self.assertFalse(self.user.check_password(ANCIEN))
        self.assertTrue(Client().login(username=EMAIL, password=NOUVEAU))
        self.assertFalse(Client().login(username=EMAIL, password=ANCIEN))

    def test_link_can_only_be_used_once(self):
        self.demander()
        lien = self.lien()
        self.choisir(self.ouvrir(lien))
        response = self.client.get(lien)
        self.assertContains(response, 'Lien invalide ou expiré')
        self.assertNotContains(response, 'name="new_password1"')

    def test_expired_link_is_refused(self):
        self.demander()
        lien = self.lien()
        with mock.patch.object(PasswordResetTokenGenerator, '_now', return_value=datetime.now() + timedelta(hours=2)):
            self.assertContains(self.client.get(lien), 'Lien invalide ou expiré')
        # encore valable avant l'expiration
        with mock.patch.object(PasswordResetTokenGenerator, '_now', return_value=datetime.now() + timedelta(minutes=30)):
            self.assertEqual(self.client.get(lien).status_code, 302)

    def test_tampered_link_is_refused(self):
        self.demander()
        lien = self.lien()
        token = lien.rstrip('/').rsplit('/', 1)[1]
        falsifie = lien.replace(token, token[:-1] + ('a' if token[-1] != 'a' else 'b'))
        self.assertContains(self.client.get(falsifie), 'Lien invalide ou expiré')

    def test_weak_passwords_are_refused_and_nothing_changes(self):
        self.demander()
        url = self.ouvrir(self.lien())
        faibles = ['court1A', 'motdepasse123', 'MotDePasseSansChiffre', '12345678']  # court, sans majuscule, sans chiffre, numérique
        for mdp in faibles:
            response = self.choisir(url, mdp)
            self.assertEqual(response.status_code, 200, mdp)
            errors = response.context['form'].errors
            self.assertIn('new_password1', errors, mdp)      # règles de robustesse : sous le mot de passe
            self.assertNotIn('new_password2', errors, mdp)   # la confirmation ne signale que les différences
        response = self.choisir(url, NOUVEAU, 'AutreMdp123')
        self.assertIn('new_password2', response.context['form'].errors)
        self.assertNotIn('new_password1', response.context['form'].errors)
        # robustesse et différence sont signalées ensemble, sans second aller-retour
        response = self.choisir(url, 'abc', 'abcd')
        self.assertIn('new_password1', response.context['form'].errors)
        self.assertIn('new_password2', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(ANCIEN))

    def test_existing_sessions_are_closed_after_a_reset(self):
        ancien_appareil = Client()
        ancien_appareil.login(username=EMAIL, password=ANCIEN)
        self.assertEqual(ancien_appareil.get(reverse('tableau_de_bord_vendeur')).status_code, 200)
        self.demander()
        self.choisir(self.ouvrir(self.lien()))
        reponse = ancien_appareil.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse('connexion_vendeur'), reponse.url)


class BrevoApiTests(ResetBase):
    """Avec BREVO_API_KEY, les e-mails partent par l'API Brevo (HTTPS) au lieu du SMTP."""

    @override_settings(
        EMAIL_BACKEND='anymail.backends.brevo.EmailBackend',
        ANYMAIL={'BREVO_API_KEY': 'cle-de-test'},
        DEFAULT_FROM_EMAIL='Djona <noreply@djona.tech>',
    )
    def test_reset_mail_is_posted_to_the_brevo_api(self):
        reponse = mock.Mock(status_code=201, content=b'{"messageId": "<1@djona.tech>"}', text='{"messageId": "<1@djona.tech>"}')
        reponse.json.return_value = {'messageId': '<1@djona.tech>'}
        with mock.patch('requests.Session.request', return_value=reponse) as requete:
            self.demander()
        self.assertEqual(requete.call_count, 1)
        _, kwargs = requete.call_args
        self.assertEqual(kwargs['method'], 'POST')
        self.assertEqual(kwargs['url'], 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(kwargs['headers']['api-key'], 'cle-de-test')
        charge = json.loads(kwargs['data'])
        self.assertEqual(charge['sender'], {'email': 'noreply@djona.tech', 'name': 'Djona'})
        self.assertEqual(charge['to'], [{'email': EMAIL}])
        self.assertIn('/reinitialisation/', charge['textContent'])
        self.assertIn('/reinitialisation/', charge['htmlContent'])

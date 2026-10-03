from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contactmessages.models import SiteContactMirror

User = get_user_model()


class SiteContactViewTest(TestCase):
    databases = {'default', 'public_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-coord', password='motdepasse', is_staff=True)
        self.url = reverse('site_contact_coordonnees')
        self.original = SiteContactMirror.objects.using('public_db').get(pk=1)

    def tearDown(self):
        self.original.save(using='public_db')

    def payload(self, **overrides):
        data = {
            'phone': '+225 07 11 22 33 44', 'whatsapp': '+225 05 55 66 77 88',
            'email': 'support@djona.tech', 'address': 'Cocody Riviera 3', 'city': 'Abidjan',
        }
        data.update(overrides)
        return data

    def test_requiert_authentification_staff(self):
        self.assertRedirects(self.client.get(self.url), f"{reverse('connexion_admin')}?next={self.url}")

    def test_affiche_les_coordonnees_actuelles(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url), self.original.email)

    def test_modification(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, self.url)
        updated = SiteContactMirror.objects.using('public_db').get(pk=1)
        self.assertEqual(updated.whatsapp, '+225 05 55 66 77 88')
        self.assertEqual(updated.address, 'Cocody Riviera 3')

    def test_numero_invalide_refuse(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload(phone='abc'))
        self.assertContains(response, 'Numéro invalide')
        self.assertEqual(SiteContactMirror.objects.using('public_db').get(pk=1).phone, self.original.phone)

    def test_whatsapp_sans_indicatif_refuse(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload(whatsapp='05 55 66 77 88'))
        self.assertContains(response, "indicatif pays")

    def test_email_invalide_refuse(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload(email='pas-un-email'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteContactMirror.objects.using('public_db').get(pk=1).email, self.original.email)

    def test_reseaux_sociaux(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload(facebook_url='https://www.facebook.com/djonagroup', tiktok_url='https://www.tiktok.com/@djonagroup'))
        self.assertRedirects(response, self.url)
        updated = SiteContactMirror.objects.using('public_db').get(pk=1)
        self.assertEqual(updated.facebook_url, 'https://www.facebook.com/djonagroup')
        self.assertEqual(updated.instagram_url, '')

    def test_lien_reseau_mauvais_domaine_refuse(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload(instagram_url='https://www.facebook.com/djonagroup'))
        self.assertContains(response, 'Ce lien doit pointer vers instagram.com.')

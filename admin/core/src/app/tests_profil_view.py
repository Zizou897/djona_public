import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from app.models import Profil

User = get_user_model()

GIF_1PX = (
    b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
    b',\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


class ProfilViewAccessTest(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('profil_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('profil_admin')}")

    def test_non_staff_is_redirected_to_login(self):
        User.objects.create_user(username='client-profil', password='motdepasse123', is_staff=False)
        self.client.login(username='client-profil', password='motdepasse123')
        response = self.client.get(reverse('profil_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('profil_admin')}")

    def test_staff_can_view_profil_and_profil_is_created(self):
        user = User.objects.create_user(username='staff-view', password='motdepasse123', is_staff=True)
        self.client.login(username='staff-view', password='motdepasse123')

        self.assertFalse(Profil.objects.filter(user=user).exists())
        response = self.client.get(reverse('profil_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profil.objects.filter(user=user).exists())

    def test_page_contains_expected_sections(self):
        User.objects.create_user(username='staff-content', password='motdepasse123', is_staff=True)
        self.client.login(username='staff-content', password='motdepasse123')

        response = self.client.get(reverse('profil_admin'))

        self.assertContains(response, 'Gestion du Profil')
        self.assertContains(response, 'Informations Personnelles')
        self.assertContains(response, 'Sécurité')
        self.assertContains(response, 'Préférences')


class ProfilViewUpdateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff-update', password='motdepasse123', is_staff=True,
            first_name='Ancien', last_name='Nom', email='ancien@example.com',
        )
        self.client.login(username='staff-update', password='motdepasse123')

    def test_post_updates_user_and_profil(self):
        response = self.client.post(reverse('profil_admin'), {
            'nom_complet': 'Koffi Konan',
            'email': 'koffi.konan@example.com',
            'telephone': '+225 07 00 00 00 00',
            'ville': Profil.Ville.ABIDJAN_COCODY,
            'two_factor_enabled': 'on',
            'langue': Profil.Langue.FRANCAIS,
            'notif_email': 'on',
        })

        self.assertRedirects(response, reverse('profil_admin'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Koffi')
        self.assertEqual(self.user.last_name, 'Konan')
        self.assertEqual(self.user.email, 'koffi.konan@example.com')

        profil = Profil.objects.get(user=self.user)
        self.assertEqual(profil.telephone, '+225 07 00 00 00 00')
        self.assertTrue(profil.two_factor_enabled)
        self.assertTrue(profil.notif_email)
        self.assertFalse(profil.notif_whatsapp)

    def test_post_with_avatar_saves_file(self):
        temp_media_root = tempfile.mkdtemp()
        with override_settings(MEDIA_ROOT=temp_media_root):
            avatar = SimpleUploadedFile('avatar.gif', GIF_1PX, content_type='image/gif')

            response = self.client.post(reverse('profil_admin'), {
                'nom_complet': 'Koffi Konan',
                'email': 'koffi.konan@example.com',
                'avatar': avatar,
            })

            self.assertRedirects(response, reverse('profil_admin'))
            profil = Profil.objects.get(user=self.user)
            self.assertTrue(profil.avatar.name.startswith('avatars/'))

    def test_post_with_invalid_email_does_not_save(self):
        response = self.client.post(reverse('profil_admin'), {
            'nom_complet': 'Koffi Konan',
            'email': 'pas-un-email',
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'ancien@example.com')


class ProfilPasswordChangeViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staff-pwd', password='ancienmdp123', is_staff=True)
        self.client.login(username='staff-pwd', password='ancienmdp123')

    def test_wrong_old_password_does_not_change_password(self):
        response = self.client.post(reverse('profil_mot_de_passe'), {
            'old_password': 'mauvais',
            'new_password1': 'nouveaumdp456',
            'new_password2': 'nouveaumdp456',
        })

        self.assertRedirects(response, reverse('profil_admin'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ancienmdp123'))

    def test_valid_password_change_keeps_session(self):
        response = self.client.post(reverse('profil_mot_de_passe'), {
            'old_password': 'ancienmdp123',
            'new_password1': 'nouveaumdp456',
            'new_password2': 'nouveaumdp456',
        })

        self.assertRedirects(response, reverse('profil_admin'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('nouveaumdp456'))

        # update_session_auth_hash a bien été appelé : la session reste valide,
        # la page suivante ne redemande pas de connexion.
        response2 = self.client.get(reverse('profil_admin'))
        self.assertEqual(response2.status_code, 200)

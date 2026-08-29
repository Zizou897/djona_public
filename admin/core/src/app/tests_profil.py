from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import Profil

User = get_user_model()


class ProfilModelTest(TestCase):
    def test_default_values(self):
        user = User.objects.create_user(username='staff-modele', password='motdepasse123')
        profil = Profil.objects.create(user=user)

        self.assertEqual(profil.ville, '')
        self.assertEqual(profil.telephone, '')
        self.assertFalse(profil.avatar)
        self.assertFalse(profil.two_factor_enabled)
        self.assertEqual(profil.langue, Profil.Langue.FRANCAIS)
        self.assertTrue(profil.notif_email)
        self.assertTrue(profil.notif_whatsapp)

    def test_str(self):
        user = User.objects.create_user(username='staff-str', password='motdepasse123')
        profil = Profil.objects.create(user=user)
        self.assertEqual(str(profil), 'Profil de staff-str')

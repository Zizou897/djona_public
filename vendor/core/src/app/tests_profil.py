from django.test import TestCase

from .models import Profil, Utilisateur


class ProfilModelTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )

    def test_valeurs_par_defaut(self):
        profil = Profil.objects.create(user=self.user)
        self.assertEqual(profil.ville, '')
        self.assertFalse(profil.avatar)
        self.assertFalse(profil.two_factor_enabled)
        self.assertEqual(profil.langue, Profil.Langue.FRANCAIS)
        self.assertTrue(profil.notif_email)
        self.assertTrue(profil.notif_whatsapp)

    def test_str(self):
        profil = Profil.objects.create(user=self.user)
        self.assertEqual(str(profil), f'Profil de {self.user}')

    def test_avatar_url_absent_sans_profil(self):
        self.assertIsNone(self.user.avatar_url)

    def test_avatar_url_absent_sans_fichier(self):
        Profil.objects.create(user=self.user)
        self.assertIsNone(self.user.avatar_url)

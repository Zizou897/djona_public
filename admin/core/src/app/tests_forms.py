from django.contrib.auth import get_user_model
from django.test import TestCase

from app.forms import ProfilForm, UtilisateurInfoForm
from app.models import Profil

User = get_user_model()


class UtilisateurInfoFormTest(TestCase):
    def test_save_splits_full_name_on_first_space(self):
        user = User.objects.create_user(username='staff-info', password='motdepasse123')
        form = UtilisateurInfoForm(data={'nom_complet': 'Koffi Konan', 'email': 'koffi@example.com'})
        self.assertTrue(form.is_valid(), form.errors)

        form.save(user)
        user.refresh_from_db()

        self.assertEqual(user.first_name, 'Koffi')
        self.assertEqual(user.last_name, 'Konan')
        self.assertEqual(user.email, 'koffi@example.com')

    def test_invalid_without_email(self):
        form = UtilisateurInfoForm(data={'nom_complet': 'Koffi Konan', 'email': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class ProfilFormTest(TestCase):
    def test_valid_data_saves(self):
        user = User.objects.create_user(username='staff-profilform', password='motdepasse123')
        profil = Profil.objects.create(user=user)

        form = ProfilForm(data={
            'telephone': '+225 07 00 00 00 00',
            'ville': Profil.Ville.ABIDJAN_COCODY,
            'two_factor_enabled': 'on',
            'langue': Profil.Langue.FRANCAIS,
            'notif_email': 'on',
        }, instance=profil)
        self.assertTrue(form.is_valid(), form.errors)

        form.save()
        profil.refresh_from_db()

        self.assertEqual(profil.telephone, '+225 07 00 00 00 00')
        self.assertEqual(profil.ville, Profil.Ville.ABIDJAN_COCODY)
        self.assertTrue(profil.two_factor_enabled)
        self.assertTrue(profil.notif_email)
        self.assertFalse(profil.notif_whatsapp)

    def test_optional_fields_can_be_blank(self):
        user = User.objects.create_user(username='staff-profilform2', password='motdepasse123')
        profil = Profil.objects.create(user=user)

        form = ProfilForm(data={}, instance=profil)
        self.assertTrue(form.is_valid(), form.errors)

        form.save()
        profil.refresh_from_db()

        self.assertEqual(profil.langue, Profil.Langue.FRANCAIS)

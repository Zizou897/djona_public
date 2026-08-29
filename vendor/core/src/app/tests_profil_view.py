import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Profil, Utilisateur

GIF_1PX = (
    b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
    b',\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


class ProfilVendeurViewAccessTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )

    def test_anonyme_est_redirige_vers_connexion(self):
        response = self.client.get(reverse('profil_vendeur'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('profil_vendeur')}")

    def test_compte_en_attente_peut_acceder_au_profil(self):
        # Gérer ses coordonnées et son mot de passe ne nécessite pas un compte
        # actif, contrairement à la gestion des annonces.
        self.client.force_login(self.user)
        response = self.client.get(reverse('profil_vendeur'))
        self.assertEqual(response.status_code, 200)

    def test_acces_cree_le_profil_sil_nexiste_pas(self):
        self.client.force_login(self.user)
        self.assertFalse(Profil.objects.filter(user=self.user).exists())
        self.client.get(reverse('profil_vendeur'))
        self.assertTrue(Profil.objects.filter(user=self.user).exists())

    def test_page_affiche_les_sections_attendues(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('profil_vendeur'))
        self.assertContains(response, 'Informations personnelles')
        self.assertContains(response, 'Sécurité')
        self.assertContains(response, 'Préférences')


class ProfilVendeurViewUpdateTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ancien@exemple.ci', password='MotDePasse1', nom='Nom', prenom='Ancien', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.user)

    def test_post_met_a_jour_utilisateur_et_profil(self):
        response = self.client.post(reverse('profil_vendeur'), {
            'nom_complet': 'Koffi Konan',
            'email': 'koffi.konan@exemple.ci',
            'telephone': '0709080706',
            'type_compte': Utilisateur.TypeCompte.PROFESSIONNEL,
            'ville': Profil.Ville.ABIDJAN_COCODY,
            'two_factor_enabled': 'on',
            'langue': Profil.Langue.FRANCAIS,
            'notif_email': 'on',
        })

        self.assertRedirects(response, reverse('profil_vendeur'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.prenom, 'Koffi')
        self.assertEqual(self.user.nom, 'Konan')
        self.assertEqual(self.user.email, 'koffi.konan@exemple.ci')
        self.assertEqual(self.user.telephone, '0709080706')
        self.assertEqual(self.user.type_compte, Utilisateur.TypeCompte.PROFESSIONNEL)

        profil = Profil.objects.get(user=self.user)
        self.assertEqual(profil.ville, Profil.Ville.ABIDJAN_COCODY)
        self.assertTrue(profil.two_factor_enabled)
        self.assertTrue(profil.notif_email)
        self.assertFalse(profil.notif_whatsapp)

    def test_post_avec_avatar_enregistre_le_fichier(self):
        temp_media_root = tempfile.mkdtemp()
        with override_settings(MEDIA_ROOT=temp_media_root):
            avatar = SimpleUploadedFile('avatar.gif', GIF_1PX, content_type='image/gif')
            response = self.client.post(reverse('profil_vendeur'), {
                'nom_complet': 'Koffi Konan',
                'email': 'koffi.konan@exemple.ci',
                'telephone': '0709080706',
                'avatar': avatar,
            })

            self.assertRedirects(response, reverse('profil_vendeur'))
            profil = Profil.objects.get(user=self.user)
            self.assertTrue(profil.avatar.name.startswith('avatars/'))

    def test_post_avec_email_invalide_ne_sauvegarde_pas(self):
        response = self.client.post(reverse('profil_vendeur'), {
            'nom_complet': 'Koffi Konan',
            'email': 'pas-un-email',
            'telephone': '0709080706',
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'ancien@exemple.ci')

    def test_post_avec_email_deja_pris_ne_sauvegarde_pas(self):
        Utilisateur.objects.create_user(
            email='deja-pris@exemple.ci', password='MotDePasse1', nom='X', prenom='Y', telephone='0102030406',
        )
        response = self.client.post(reverse('profil_vendeur'), {
            'nom_complet': 'Koffi Konan',
            'email': 'deja-pris@exemple.ci',
            'telephone': '0709080706',
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'ancien@exemple.ci')


class ProfilPasswordChangeViewTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='AncienMdp123', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        self.client.force_login(self.user)

    def test_mauvais_ancien_mot_de_passe_ne_change_rien(self):
        response = self.client.post(reverse('profil_vendeur_mot_de_passe'), {
            'old_password': 'mauvais',
            'new_password1': 'NouveauMdp456',
            'new_password2': 'NouveauMdp456',
        })

        self.assertRedirects(response, reverse('profil_vendeur'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('AncienMdp123'))

    def test_changement_valide_garde_la_session(self):
        response = self.client.post(reverse('profil_vendeur_mot_de_passe'), {
            'old_password': 'AncienMdp123',
            'new_password1': 'NouveauMdp456',
            'new_password2': 'NouveauMdp456',
        })

        self.assertRedirects(response, reverse('profil_vendeur'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NouveauMdp456'))

        # update_session_auth_hash a bien été appelé : la session reste
        # valide, la page suivante ne redemande pas de connexion.
        response2 = self.client.get(reverse('profil_vendeur'))
        self.assertEqual(response2.status_code, 200)

    def test_requiert_authentification(self):
        self.client.logout()
        response = self.client.post(reverse('profil_vendeur_mot_de_passe'), {})
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('profil_vendeur_mot_de_passe')}")

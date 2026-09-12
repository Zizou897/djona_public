from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from annonces.models import Annonce
from .forms import ConnexionForm, InscriptionForm
from .models import Profil, Utilisateur

# Le plus petit PNG valide possible (1x1 pixel transparent) — nécessaire pour
# que la validation Pillow (forms.ImageField) accepte le fichier comme une
# vraie image.
PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00'
    b'\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class UtilisateurModelTest(TestCase):
    def test_create_user_hashes_password(self):
        user = Utilisateur.objects.create_user(
            email='Ange@Exemple.CI',
            password='MotDePasse1',
            nom='Koffi',
            prenom='Ange',
            telephone='0102030405',
        )
        # normalize_email only lowercases the domain part (RFC-correct);
        # the local part is preserved as-is.
        self.assertEqual(user.email, 'Ange@exemple.ci')
        self.assertNotEqual(user.password, 'MotDePasse1')
        self.assertTrue(user.check_password('MotDePasse1'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_new_user_starts_en_attente(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405',
        )
        self.assertEqual(user.statut_compte, Utilisateur.StatutCompte.EN_ATTENTE)

    def test_create_superuser_sets_flags(self):
        admin = Utilisateur.objects.create_superuser(email='root@djona.ci', password='MotDePasse1')
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_create_superuser_rejects_is_staff_false(self):
        with self.assertRaises(ValueError):
            Utilisateur.objects.create_superuser(email='root@djona.ci', password='MotDePasse1', is_staff=False)


class InscriptionFormTest(TestCase):
    def valid_data(self, **overrides):
        data = {
            'nom': 'Koffi',
            'prenom': 'Ange',
            'email': 'ange@exemple.ci',
            'telephone': '0102030405',
            'type_compte': Utilisateur.TypeCompte.PARTICULIER,
            'password': 'MotDePasse1',
            'consentement': True,
        }
        data.update(overrides)
        return data

    def test_valid_data_creates_user(self):
        form = InscriptionForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.pk)
        self.assertTrue(user.check_password('MotDePasse1'))

    def test_rejects_duplicate_email(self):
        Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        form = InscriptionForm(data=self.valid_data())
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_rejects_password_without_uppercase(self):
        form = InscriptionForm(data=self.valid_data(password='motdepasse1'))
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_rejects_password_without_digit(self):
        form = InscriptionForm(data=self.valid_data(password='MotDePasseSansChiffre'))
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_rejects_short_password(self):
        form = InscriptionForm(data=self.valid_data(password='Mdp1'))
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_requires_consentement(self):
        form = InscriptionForm(data=self.valid_data(consentement=False))
        self.assertFalse(form.is_valid())
        self.assertIn('consentement', form.errors)

    def test_rejects_invalid_telephone(self):
        form = InscriptionForm(data=self.valid_data(telephone='abc'))
        self.assertFalse(form.is_valid())
        self.assertIn('telephone', form.errors)

    def test_professionnel_requiert_raison_sociale_rccm_et_adresse(self):
        form = InscriptionForm(data=self.valid_data(type_compte=Utilisateur.TypeCompte.PROFESSIONNEL))
        self.assertFalse(form.is_valid())
        self.assertIn('raison_sociale', form.errors)
        self.assertIn('numero_rccm', form.errors)
        self.assertIn('adresse', form.errors)

    def test_professionnel_valide_cree_un_profil_non_verifie(self):
        form = InscriptionForm(data=self.valid_data(
            type_compte=Utilisateur.TypeCompte.PROFESSIONNEL,
            raison_sociale='Ivoire Auto Prestige SARL',
            numero_rccm='CI-ABJ-2026-B-12345',
            adresse='Boulevard VGE, Marcory, Abidjan',
        ))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        profil = Profil.objects.get(user=user)
        self.assertEqual(profil.raison_sociale, 'Ivoire Auto Prestige SARL')
        self.assertEqual(profil.numero_rccm, 'CI-ABJ-2026-B-12345')
        self.assertEqual(profil.adresse, 'Boulevard VGE, Marcory, Abidjan')
        self.assertFalse(profil.entreprise_verifiee)

    def test_professionnel_avec_logo_enregistre_lavatar(self):
        logo = SimpleUploadedFile('logo.png', PNG_1PX, content_type='image/png')
        form = InscriptionForm(data=self.valid_data(
            type_compte=Utilisateur.TypeCompte.PROFESSIONNEL,
            raison_sociale='Ivoire Auto Prestige SARL',
            numero_rccm='CI-ABJ-2026-B-12345',
            adresse='Boulevard VGE, Marcory, Abidjan',
        ), files={'logo': logo})
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        profil = Profil.objects.get(user=user)
        self.assertTrue(profil.avatar)

    def test_particulier_ne_cree_pas_de_profil(self):
        form = InscriptionForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertFalse(Profil.objects.filter(user=user).exists())


class ConnexionFormTest(TestCase):
    def test_username_field_uses_email_widget(self):
        form = ConnexionForm()
        self.assertEqual(form.fields['username'].label, 'Adresse email')


class InscriptionViewTest(TestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse('inscription_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rejoignez Djona')

    def test_post_valid_data_creates_and_logs_in_user(self):
        response = self.client.post(reverse('inscription_vendeur'), {
            'nom': 'Koffi',
            'prenom': 'Ange',
            'email': 'ange@exemple.ci',
            'telephone': '0102030405',
            'type_compte': Utilisateur.TypeCompte.PARTICULIER,
            'password': 'MotDePasse1',
            'consentement': True,
        })
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))
        self.assertTrue(Utilisateur.objects.filter(email='ange@exemple.ci').exists())
        # form_valid() auto-logs the new user in, so this follow-up GET
        # should not bounce back to the login page.
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected_away_from_inscription(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('inscription_vendeur'))
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))


class ConnexionViewTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )

    def test_get_renders_form(self):
        response = self.client.get(reverse('connexion_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bienvenue')

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post(reverse('connexion_vendeur'), {
            'username': 'ange@exemple.ci',
            'password': 'MotDePasse1',
        })
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))

    def test_invalid_login_shows_error(self):
        response = self.client.post(reverse('connexion_vendeur'), {
            'username': 'ange@exemple.ci',
            'password': 'mauvais-mot-de-passe',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email ou mot de passe incorrect.')


class TableauDeBordVendeurViewTest(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('tableau_de_bord_vendeur')}")

    def test_compte_en_attente_montre_message_attente(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'en cours de validation')
        self.assertNotContains(response, 'Mes annonces')

    def test_compte_suspendu_montre_message_suspension(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        user.statut_compte = Utilisateur.StatutCompte.SUSPENDU
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'suspendu')
        self.assertNotContains(response, 'Mes annonces')

    def test_compte_actif_montre_dashboard_complet(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        user.statut_compte = Utilisateur.StatutCompte.ACTIF
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bonjour, Ange')
        self.assertContains(response, 'Créer votre première annonce')

    def annonce_data(self, vendeur, **overrides):
        data = {
            'vendeur': vendeur, 'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019,
            'prix': 8500000, 'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état.',
        }
        data.update(overrides)
        return data

    def test_compte_actif_sans_annonce_affiche_etat_vide(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertContains(response, 'Créez votre première annonce')
        self.assertEqual(response.context['nb_annonces'], 0)

    def test_compte_actif_avec_annonces_affiche_les_compteurs_et_recentes(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        Annonce.objects.create(**self.annonce_data(user, statut=Annonce.Statut.BROUILLON))
        Annonce.objects.create(**self.annonce_data(user, statut=Annonce.Statut.EN_ATTENTE))
        Annonce.objects.create(**self.annonce_data(user, statut=Annonce.Statut.PUBLIEE, modele='Yaris'))
        Annonce.objects.create(**self.annonce_data(user, statut=Annonce.Statut.REFUSEE))
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.context['nb_annonces'], 4)
        self.assertEqual(response.context['nb_brouillons'], 1)
        self.assertEqual(response.context['nb_en_attente'], 1)
        self.assertEqual(response.context['nb_publiees'], 1)
        self.assertEqual(response.context['nb_refusees'], 1)
        self.assertContains(response, 'Yaris')
        self.assertContains(response, 'Voir tout')

    def test_compte_actif_annonces_recentes_scopees_au_vendeur(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        autre_vendeur = Utilisateur.objects.create_user(
            email='autre@exemple.ci', password='MotDePasse1', nom='Diallo', prenom='Fatou', telephone='0102030406',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        Annonce.objects.create(**self.annonce_data(autre_vendeur, modele='Tiguan'))
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.context['nb_annonces'], 0)
        self.assertNotContains(response, 'Tiguan')

import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DemandePassagePro, Profil, Utilisateur

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
        # Le type de compte n'est pas modifiable depuis le profil : la valeur envoyée est ignorée.
        self.assertEqual(self.user.type_compte, Utilisateur.TypeCompte.PARTICULIER)

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


class ProfilVendeurChampsEntrepriseTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.user)

    def donnees(self, type_compte):
        return {
            'nom_complet': 'Ange Koffi', 'email': 'ange@exemple.ci', 'telephone': '0102030405',
            'type_compte': type_compte, 'langue': Profil.Langue.FRANCAIS,
            'raison_sociale': 'Ivoire Auto SARL', 'numero_rccm': 'CI-ABJ-2026-B-12345', 'adresse': 'Marcory',
        }

    def test_particulier_ne_voit_pas_le_bloc_entreprise(self):
        response = self.client.get(reverse('profil_vendeur'))
        self.assertNotContains(response, 'id="champs-entreprise"')
        self.assertNotContains(response, 'id="id_numero_rccm"')
        self.assertNotContains(response, 'name="type_compte"')

    def test_particulier_ne_peut_pas_enregistrer_d_infos_entreprise(self):
        # Même en se déclarant « professionnel » dans la requête.
        response = self.client.post(reverse('profil_vendeur'), self.donnees(Utilisateur.TypeCompte.PROFESSIONNEL))
        self.assertRedirects(response, reverse('profil_vendeur'))
        profil = Profil.objects.get(user=self.user)
        self.assertEqual(profil.raison_sociale, '')
        self.assertEqual(profil.numero_rccm, '')
        self.assertEqual(profil.adresse, '')
        self.user.refresh_from_db()
        self.assertEqual(self.user.type_compte, Utilisateur.TypeCompte.PARTICULIER)

    def test_professionnel_enregistre_ses_infos_entreprise(self):
        self.user.type_compte = Utilisateur.TypeCompte.PROFESSIONNEL
        self.user.save()
        response = self.client.get(reverse('profil_vendeur'))
        self.assertContains(response, 'id="champs-entreprise"')
        response = self.client.post(reverse('profil_vendeur'), self.donnees(Utilisateur.TypeCompte.PROFESSIONNEL))
        self.assertRedirects(response, reverse('profil_vendeur'))
        profil = Profil.objects.get(user=self.user)
        self.assertEqual(profil.raison_sociale, 'Ivoire Auto SARL')
        self.assertEqual(profil.numero_rccm, 'CI-ABJ-2026-B-12345')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DemandePassageProTest(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.user)

    def donnees(self, **overrides):
        data = {
            'raison_sociale': 'Ivoire Auto SARL', 'numero_rccm': 'CI-ABJ-2026-B-12345', 'adresse': 'Marcory',
            'message': 'Concession de 30 véhicules.',
            'justificatif_rccm': SimpleUploadedFile('rccm.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
        }
        data.update(overrides)
        return data

    def test_particulier_voit_la_demande_de_passage_pro(self):
        response = self.client.get(reverse('profil_vendeur'))
        self.assertContains(response, 'Passer à un compte professionnel')
        self.assertContains(response, reverse('profil_vendeur_demande_pro'))

    def test_envoi_cree_une_demande_en_attente_sans_changer_le_compte(self):
        response = self.client.post(reverse('profil_vendeur_demande_pro'), self.donnees())
        self.assertRedirects(response, reverse('profil_vendeur'))
        demande = DemandePassagePro.objects.get(utilisateur=self.user)
        self.assertEqual(demande.statut, DemandePassagePro.Statut.EN_ATTENTE)
        self.assertEqual(demande.raison_sociale, 'Ivoire Auto SARL')
        self.assertTrue(demande.justificatif_rccm.name.startswith('justificatifs/'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.type_compte, Utilisateur.TypeCompte.PARTICULIER)
        self.assertContains(self.client.get(reverse('profil_vendeur')), "en cours d'examen")

    def test_justificatif_obligatoire(self):
        donnees = self.donnees()
        del donnees['justificatif_rccm']
        response = self.client.post(reverse('profil_vendeur_demande_pro'), donnees)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DemandePassagePro.objects.exists())

    def test_une_seule_demande_en_attente_a_la_fois(self):
        self.client.post(reverse('profil_vendeur_demande_pro'), self.donnees())
        self.client.post(reverse('profil_vendeur_demande_pro'), self.donnees(raison_sociale='Autre SARL'))
        self.assertEqual(DemandePassagePro.objects.filter(utilisateur=self.user).count(), 1)

    def test_nouvelle_demande_possible_apres_un_refus(self):
        self.client.post(reverse('profil_vendeur_demande_pro'), self.donnees())
        DemandePassagePro.objects.update(statut=DemandePassagePro.Statut.REFUSEE, motif_refus='RCCM illisible')
        self.assertContains(self.client.get(reverse('profil_vendeur')), 'RCCM illisible')
        self.client.post(reverse('profil_vendeur_demande_pro'), self.donnees())
        self.assertEqual(DemandePassagePro.objects.filter(statut=DemandePassagePro.Statut.EN_ATTENTE).count(), 1)

    def test_compte_professionnel_ne_peut_pas_faire_de_demande(self):
        self.user.type_compte = Utilisateur.TypeCompte.PROFESSIONNEL
        self.user.save()
        self.assertNotContains(self.client.get(reverse('profil_vendeur')), 'Passer à un compte professionnel')
        self.client.post(reverse('profil_vendeur_demande_pro'), self.donnees())
        self.assertFalse(DemandePassagePro.objects.exists())

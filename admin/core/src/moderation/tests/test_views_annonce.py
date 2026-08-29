from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from moderation.models import AnnonceMirror, CompteVendeur

User = get_user_model()


class AnnonceModerationListViewTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='motdepasse', is_staff=True)
        self.vendeur = CompteVendeur.objects.using('vendor_db').create(
            email='mod-vendeur@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )
        self.annonce_en_attente = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Toyota', modele='Corolla', annee=2019, prix=8500000,
            kilometrage=45000, carburant='essence', boite_vitesses='automatique', couleur='Gris',
            description='Très bon état.', statut=AnnonceMirror.Statut.EN_ATTENTE,
            created_at='2026-08-27T10:00:00Z', update_at='2026-08-27T10:00:00Z',
        )
        self.annonce_brouillon = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Honda', modele='Civic', annee=2020, prix=9500000,
            kilometrage=30000, carburant='essence', boite_vitesses='manuelle', couleur='Noir',
            description='Comme neuve.', statut=AnnonceMirror.Statut.BROUILLON,
            created_at='2026-08-27T09:00:00Z', update_at='2026-08-27T09:00:00Z',
        )
        self.annonce_publiee = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Ford', modele='Fiesta', annee=2018, prix=6500000,
            kilometrage=60000, carburant='diesel', boite_vitesses='manuelle', couleur='Blanc',
            description='Déjà en ligne.', statut=AnnonceMirror.Statut.PUBLIEE,
            created_at='2026-08-27T08:00:00Z', update_at='2026-08-27T08:00:00Z',
        )

    def tearDown(self):
        AnnonceMirror.objects.using('vendor_db').filter(vendeur=self.vendeur).delete()
        CompteVendeur.objects.using('vendor_db').filter(pk=self.vendeur.pk).delete()

    def test_requiert_authentification_staff(self):
        response = self.client.get(reverse('annonce_moderation_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('annonce_moderation_liste')}")

    def test_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin-liste', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        response = self.client.get(reverse('annonce_moderation_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('annonce_moderation_liste')}")

    def test_liste_seulement_les_annonces_en_attente(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_moderation_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Corolla')
        self.assertNotContains(response, 'Civic')

    def test_detail_affiche_les_infos_completes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_moderation_detail', args=[self.annonce_en_attente.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota')
        self.assertContains(response, 'Ange')
        self.assertContains(response, '8500000')

    def test_detail_affiche_carburant_et_boite_vitesses_lisibles(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_moderation_detail', args=[self.annonce_en_attente.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Essence')
        self.assertContains(response, 'Automatique')

    def test_detail_anonyme_est_redirige(self):
        url = reverse('annonce_moderation_detail', args=[self.annonce_en_attente.pk])
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_detail_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin-detail', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        url = reverse('annonce_moderation_detail', args=[self.annonce_en_attente.pk])
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_valider_publie_lannonce(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_valider', args=[self.annonce_en_attente.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_en_attente.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_en_attente.statut, AnnonceMirror.Statut.PUBLIEE)

    def test_refuser_change_le_statut(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_refuser', args=[self.annonce_en_attente.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_en_attente.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_en_attente.statut, AnnonceMirror.Statut.REFUSEE)

    def test_valider_ne_change_pas_le_statut_dun_brouillon(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_valider', args=[self.annonce_brouillon.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_brouillon.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_brouillon.statut, AnnonceMirror.Statut.BROUILLON)

    def test_valider_ne_change_pas_le_statut_dune_annonce_deja_publiee(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_valider', args=[self.annonce_publiee.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_publiee.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_publiee.statut, AnnonceMirror.Statut.PUBLIEE)

    def test_refuser_ne_change_pas_le_statut_dun_brouillon(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_refuser', args=[self.annonce_brouillon.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_brouillon.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_brouillon.statut, AnnonceMirror.Statut.BROUILLON)

    def test_refuser_ne_change_pas_le_statut_dune_annonce_deja_publiee(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_refuser', args=[self.annonce_publiee.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_publiee.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_publiee.statut, AnnonceMirror.Statut.PUBLIEE)

    def test_valider_refuse_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_valider', args=[self.annonce_en_attente.pk]))
        self.assertEqual(response.status_code, 405)

    def test_refuser_refuse_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_refuser', args=[self.annonce_en_attente.pk]))
        self.assertEqual(response.status_code, 405)

    def test_valider_anonyme_est_redirige(self):
        url = reverse('annonce_valider', args=[self.annonce_en_attente.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_valider_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin-valider', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        url = reverse('annonce_valider', args=[self.annonce_en_attente.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_refuser_anonyme_est_redirige(self):
        url = reverse('annonce_refuser', args=[self.annonce_en_attente.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_refuser_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin-refuser', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        url = reverse('annonce_refuser', args=[self.annonce_en_attente.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

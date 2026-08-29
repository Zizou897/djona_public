from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from moderation.models import CompteVendeur

User = get_user_model()


class VendeurListViewTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='motdepasse', is_staff=True)
        self.vendeur_attente = CompteVendeur.objects.using('vendor_db').create(
            email='attente@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.EN_ATTENTE,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )
        self.vendeur_actif = CompteVendeur.objects.using('vendor_db').create(
            email='actif@exemple.ci', nom='Diallo', prenom='Fatou', telephone='0102030406',
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL,
            statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-26T10:00:00Z', password='inutilise',
        )

    def tearDown(self):
        CompteVendeur.objects.using('vendor_db').filter(
            email__in=['attente@exemple.ci', 'actif@exemple.ci'],
        ).delete()

    def test_requiert_authentification_staff(self):
        response = self.client.get(reverse('vendeur_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('vendeur_liste')}")

    def test_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        response = self.client.get(reverse('vendeur_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('vendeur_liste')}")

    def test_liste_les_vendeurs_en_attente_en_premier(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('vendeur_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ange')
        self.assertContains(response, 'Fatou')
        content = response.content.decode()
        self.assertLess(content.index('Ange'), content.index('Fatou'))

    def test_activer_change_le_statut(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('vendeur_activer', args=[self.vendeur_attente.pk]))
        self.assertRedirects(response, reverse('vendeur_liste'))
        self.vendeur_attente.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur_attente.statut_compte, CompteVendeur.StatutCompte.ACTIF)

    def test_suspendre_change_le_statut(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('vendeur_suspendre', args=[self.vendeur_actif.pk]))
        self.assertRedirects(response, reverse('vendeur_liste'))
        self.vendeur_actif.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur_actif.statut_compte, CompteVendeur.StatutCompte.SUSPENDU)

    def test_activer_refuse_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('vendeur_activer', args=[self.vendeur_attente.pk]))
        self.assertEqual(response.status_code, 405)

    def test_suspendre_refuse_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('vendeur_suspendre', args=[self.vendeur_actif.pk]))
        self.assertEqual(response.status_code, 405)

    def test_activer_anonyme_est_redirige(self):
        url = reverse('vendeur_activer', args=[self.vendeur_attente.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_activer_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin-activer', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        url = reverse('vendeur_activer', args=[self.vendeur_attente.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_suspendre_anonyme_est_redirige(self):
        url = reverse('vendeur_suspendre', args=[self.vendeur_actif.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

    def test_suspendre_non_staff_est_redirige(self):
        non_staff = User.objects.create_user(username='pas-admin-suspendre', password='motdepasse', is_staff=False)
        self.client.force_login(non_staff)
        url = reverse('vendeur_suspendre', args=[self.vendeur_actif.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={url}")

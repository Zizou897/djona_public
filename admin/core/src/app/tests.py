from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from moderation.models import AnnonceMirror, CompteVendeur

User = get_user_model()


class AdminDashboardViewAccessTest(TestCase):
    # test_staff_can_view_dashboard exerce AdminDashboardView, dont
    # get_context_data() interroge désormais 'vendor_db' (compteurs, listes) même
    # sans données vendeur/annonce en base — l'alias doit donc être autorisé ici,
    # pas seulement sur AdminDashboardViewDataTest ci-dessous.
    databases = {'default', 'vendor_db'}

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('dashboard_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('dashboard_admin')}")

    def test_non_staff_is_redirected_to_login(self):
        User.objects.create_user(username='client', password='motdepasse123', is_staff=False)
        self.client.login(username='client', password='motdepasse123')
        response = self.client.get(reverse('dashboard_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('dashboard_admin')}")

    def test_staff_can_view_dashboard(self):
        User.objects.create_user(username='staff', password='motdepasse123', is_staff=True)
        self.client.login(username='staff', password='motdepasse123')
        response = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(response.status_code, 200)


class AdminDashboardViewDataTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='staff-dash', password='motdepasse123', is_staff=True)
        self.client.login(username='staff-dash', password='motdepasse123')

        self.vendeur_particulier = CompteVendeur.objects.using('vendor_db').create(
            email='dash-particulier@exemple.ci', nom='Kone', prenom='Awa', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-20T10:00:00Z', password='inutilise',
        )
        self.vendeur_pro = CompteVendeur.objects.using('vendor_db').create(
            email='dash-pro@exemple.ci', nom='Traore', prenom='Issa', telephone='0102030406',
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T09:00:00Z', password='inutilise',
        )

    def tearDown(self):
        AnnonceMirror.objects.using('vendor_db').filter(
            vendeur__in=[self.vendeur_particulier, self.vendeur_pro]
        ).delete()
        CompteVendeur.objects.using('vendor_db').filter(
            pk__in=[self.vendeur_particulier.pk, self.vendeur_pro.pk]
        ).delete()

    def _creer_annonce(self, statut, created_at, marque='Toyota'):
        return AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur_particulier, marque=marque, modele='Corolla', annee=2019, prix=8500000,
            kilometrage=45000, carburant='essence', boite_vitesses='automatique', couleur='Gris',
            description='Test.', statut=statut, created_at=created_at, update_at=created_at,
        )

    def test_kpi_counts_reflect_real_data(self):
        self._creer_annonce(AnnonceMirror.Statut.PUBLIEE, '2026-08-27T08:00:00Z')
        self._creer_annonce(AnnonceMirror.Statut.PUBLIEE, '2026-08-27T08:00:00Z')
        self._creer_annonce(AnnonceMirror.Statut.EN_ATTENTE, '2026-08-27T09:00:00Z')

        response = self.client.get(reverse('dashboard_admin'))

        self.assertEqual(response.context['annonces_publiees'], 2)
        self.assertEqual(response.context['annonces_en_attente_total'], 1)
        self.assertEqual(response.context['annonces_total'], 3)
        self.assertEqual(response.context['vendeurs_particuliers'], 1)
        self.assertEqual(response.context['vendeurs_professionnels'], 1)
        self.assertEqual(response.context['vendeurs_total'], 2)

    def test_pending_list_shows_only_en_attente_limited_to_five(self):
        self._creer_annonce(AnnonceMirror.Statut.PUBLIEE, '2026-08-27T08:00:00Z', marque='Publiee')
        self._creer_annonce(AnnonceMirror.Statut.REFUSEE, '2026-08-27T08:00:00Z', marque='Refusee')
        for i in range(6):
            self._creer_annonce(AnnonceMirror.Statut.EN_ATTENTE, f'2026-08-2{i}T09:00:00Z', marque=f'Attente{i}')

        response = self.client.get(reverse('dashboard_admin'))

        annonces_en_attente = response.context['annonces_en_attente']
        self.assertEqual(len(annonces_en_attente), 5)
        self.assertTrue(all(a.statut == AnnonceMirror.Statut.EN_ATTENTE for a in annonces_en_attente))
        # Les annonces 'Publiee'/'Refusee' apparaissent légitimement dans la
        # carte "Activité récente" (qui liste les annonces de tout statut) :
        # on isole donc la carte "Validation en attente" pour vérifier
        # qu'elle seule ne les affiche pas.
        content = response.content.decode()
        carte_validation = content.split('Validation en attente', 1)[1].split('Activité récente', 1)[0]
        self.assertNotIn('Publiee', carte_validation)
        self.assertNotIn('Refusee', carte_validation)
        # la plus récente (Attente5, 2026-08-25) doit être en tête
        self.assertEqual(annonces_en_attente[0].marque, 'Attente5')

    def test_recent_activity_combines_and_sorts_by_date(self):
        self._creer_annonce(AnnonceMirror.Statut.EN_ATTENTE, '2026-08-26T09:00:00Z', marque='Recente')

        response = self.client.get(reverse('dashboard_admin'))

        activites = response.context['activites_recentes']
        self.assertTrue(len(activites) >= 2)
        # vendeur_pro (27 août) inscrit après l'annonce (26 août) -> doit être en tête
        self.assertEqual(activites[0]['type'], 'inscription')
        self.assertIn('Issa', activites[0]['description'])

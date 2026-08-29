from django.test import TestCase
from django.urls import reverse

from app.models import Utilisateur
from annonces.models import Annonce


class AnnonceCreateViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def annonce_data(self, **overrides):
        data = {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 8500000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état.',
        }
        data.update(overrides)
        return data

    def test_requiert_authentification(self):
        self.client.logout()
        response = self.client.get(reverse('annonce_creer'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('annonce_creer')}")

    def test_compte_en_attente_ne_peut_pas_creer(self):
        self.vendeur.statut_compte = Utilisateur.StatutCompte.EN_ATTENTE
        self.vendeur.save()
        response = self.client.get(reverse('annonce_creer'))
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))

    def test_creation_sans_action_sauvegarde_en_brouillon(self):
        response = self.client.post(reverse('annonce_creer'), self.annonce_data(action='enregistrer'))
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce = Annonce.objects.get(vendeur=self.vendeur)
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)

    def test_creation_avec_action_soumettre_passe_en_attente(self):
        response = self.client.post(reverse('annonce_creer'), self.annonce_data(action='soumettre'))
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce = Annonce.objects.get(vendeur=self.vendeur)
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_vendeur_est_toujours_utilisateur_connecte(self):
        self.client.post(reverse('annonce_creer'), self.annonce_data(action='enregistrer'))
        annonce = Annonce.objects.get(vendeur=self.vendeur)
        self.assertEqual(annonce.vendeur, self.vendeur)


class AnnoncePublierViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.autre_vendeur = Utilisateur.objects.create_user(
            email='autre@exemple.ci', password='MotDePasse1', nom='Diallo', prenom='Fatou',
            telephone='0102030406', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def create_annonce(self, vendeur=None, statut=Annonce.Statut.BROUILLON):
        return Annonce.objects.create(
            vendeur=vendeur or self.vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Gris',
            description='Très bon état.', statut=statut,
        )

    def test_publier_un_brouillon_passe_en_attente(self):
        annonce = self.create_annonce()
        response = self.client.post(reverse('annonce_publier', args=[annonce.pk]))
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_publier_une_annonce_deja_en_attente_ne_fait_rien(self):
        annonce = self.create_annonce(statut=Annonce.Statut.EN_ATTENTE)
        self.client.post(reverse('annonce_publier', args=[annonce.pk]))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_publier_refuse_get(self):
        annonce = self.create_annonce()
        response = self.client.get(reverse('annonce_publier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 405)

    def test_annonce_dun_autre_vendeur_renvoie_404(self):
        annonce = self.create_annonce(vendeur=self.autre_vendeur)
        response = self.client.post(reverse('annonce_publier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 404)


class MesAnnoncesListViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.autre_vendeur = Utilisateur.objects.create_user(
            email='autre@exemple.ci', password='MotDePasse1', nom='Diallo', prenom='Fatou',
            telephone='0102030406', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )

    def create_annonce(self, vendeur, statut=Annonce.Statut.EN_ATTENTE):
        return Annonce.objects.create(
            vendeur=vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Gris',
            description='Très bon état.', statut=statut,
        )

    def test_requiert_authentification(self):
        response = self.client.get(reverse('mes_annonces'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('mes_annonces')}")

    def test_compte_en_attente_est_redirige(self):
        vendeur_en_attente = Utilisateur.objects.create_user(
            email='attente@exemple.ci', password='MotDePasse1', nom='X', prenom='Y', telephone='0102030407',
        )
        self.client.force_login(vendeur_en_attente)
        response = self.client.get(reverse('mes_annonces'))
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))

    def test_ne_montre_que_les_annonces_du_vendeur_connecte(self):
        self.create_annonce(self.vendeur)
        self.create_annonce(self.autre_vendeur)
        self.client.force_login(self.vendeur)
        response = self.client.get(reverse('mes_annonces'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['annonces']), 1)
        self.assertEqual(response.context['annonces'][0].vendeur, self.vendeur)

    def test_page_vide_affiche_message_invitation(self):
        self.client.force_login(self.vendeur)
        response = self.client.get(reverse('mes_annonces'))
        self.assertContains(response, "Vous n'avez pas encore d'annonce")

    def test_stats_context_compte_toutes_les_annonces_du_vendeur(self):
        self.create_annonce(self.vendeur, statut=Annonce.Statut.BROUILLON)
        self.create_annonce(self.vendeur, statut=Annonce.Statut.EN_ATTENTE)
        self.create_annonce(self.vendeur, statut=Annonce.Statut.PUBLIEE)
        self.create_annonce(self.vendeur, statut=Annonce.Statut.REFUSEE)
        self.create_annonce(self.autre_vendeur, statut=Annonce.Statut.PUBLIEE)
        self.client.force_login(self.vendeur)
        response = self.client.get(reverse('mes_annonces'))
        self.assertEqual(response.context['nb_total'], 4)
        self.assertEqual(response.context['nb_publiees'], 1)
        self.assertEqual(response.context['nb_en_attente'], 1)
        self.assertEqual(response.context['nb_refusees'], 1)

    def test_filtre_par_statut_ne_montre_que_ce_statut(self):
        self.create_annonce(self.vendeur, statut=Annonce.Statut.BROUILLON)
        self.create_annonce(self.vendeur, statut=Annonce.Statut.PUBLIEE)
        self.client.force_login(self.vendeur)
        response = self.client.get(reverse('mes_annonces'), {'statut': 'publiee'})
        self.assertEqual(len(response.context['annonces']), 1)
        self.assertEqual(response.context['annonces'][0].statut, Annonce.Statut.PUBLIEE)
        # Les stats globales restent inchangées par le filtre.
        self.assertEqual(response.context['nb_total'], 2)

    def test_recherche_filtre_par_marque_ou_modele_insensible_a_la_casse(self):
        self.create_annonce(self.vendeur, statut=Annonce.Statut.BROUILLON)  # Toyota Corolla
        Annonce.objects.create(
            vendeur=self.vendeur, marque='Mercedes-Benz', modele='C300', annee=2020,
            prix=22000000, kilometrage=30000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Noir',
            description='Excellent état.', statut=Annonce.Statut.PUBLIEE,
        )
        self.client.force_login(self.vendeur)
        response = self.client.get(reverse('mes_annonces'), {'q': 'mercedes'})
        self.assertEqual(len(response.context['annonces']), 1)
        self.assertEqual(response.context['annonces'][0].marque, 'Mercedes-Benz')

    def test_tri_par_prix_croissant(self):
        Annonce.objects.create(
            vendeur=self.vendeur, marque='Toyota', modele='Yaris', annee=2018,
            prix=5000000, kilometrage=60000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.MANUELLE, couleur='Blanc',
            description='Économique.', statut=Annonce.Statut.PUBLIEE,
        )
        self.create_annonce(self.vendeur, statut=Annonce.Statut.PUBLIEE)  # prix=8500000
        self.client.force_login(self.vendeur)
        response = self.client.get(reverse('mes_annonces'), {'tri': 'prix_croissant'})
        prix = [a.prix for a in response.context['annonces']]
        self.assertEqual(prix, sorted(prix))


class AnnonceUpdateViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.autre_vendeur = Utilisateur.objects.create_user(
            email='autre@exemple.ci', password='MotDePasse1', nom='Diallo', prenom='Fatou',
            telephone='0102030406', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def create_annonce(self, vendeur=None, statut=Annonce.Statut.BROUILLON):
        return Annonce.objects.create(
            vendeur=vendeur or self.vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Gris',
            description='Très bon état.', statut=statut,
        )

    def test_brouillon_est_modifiable(self):
        annonce = self.create_annonce()
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 200)

    def test_edition_annonce_refusee_repasse_en_brouillon(self):
        annonce = self.create_annonce(statut=Annonce.Statut.REFUSEE)
        response = self.client.post(reverse('annonce_modifier', args=[annonce.pk]), {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 9000000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état, prix ajusté.',
        })
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertEqual(annonce.prix, 9000000)

    def test_en_attente_non_modifiable(self):
        annonce = self.create_annonce(statut=Annonce.Statut.EN_ATTENTE)
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertRedirects(response, reverse('mes_annonces'))

    def test_publiee_non_modifiable(self):
        annonce = self.create_annonce(statut=Annonce.Statut.PUBLIEE)
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertRedirects(response, reverse('mes_annonces'))

    def test_annonce_dun_autre_vendeur_renvoie_404(self):
        annonce = self.create_annonce(vendeur=self.autre_vendeur)
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 404)

    def test_requiert_authentification(self):
        self.client.logout()
        annonce = self.create_annonce()
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('annonce_modifier', args=[annonce.pk])}")

    def test_edition_brouillon_via_post_fonctionne(self):
        annonce = self.create_annonce(statut=Annonce.Statut.BROUILLON)
        response = self.client.post(reverse('annonce_modifier', args=[annonce.pk]), {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 8700000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état.',
        })
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertEqual(annonce.prix, 8700000)

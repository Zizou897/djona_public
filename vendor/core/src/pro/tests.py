from django.test import TestCase
from django.urls import reverse

from annonces.models import Annonce
from app.models import Utilisateur

from .models import MembreEquipe, Prospect


def creer_pro(email='pro@exemple.ci', **overrides):
    data = {
        'email': email, 'password': 'MotDePasse1', 'nom': 'Traore', 'prenom': 'Awa',
        'telephone': '0102030405', 'type_compte': Utilisateur.TypeCompte.PROFESSIONNEL,
        'statut_compte': Utilisateur.StatutCompte.ACTIF,
    }
    data.update(overrides)
    return Utilisateur.objects.create_user(**data)


class EspaceProAccesTest(TestCase):
    def setUp(self):
        self.pro = creer_pro()
        self.particulier = Utilisateur.objects.create_user(
            email='particulier@exemple.ci', password='MotDePasse1', nom='Kone', prenom='Yao',
            telephone='0102030406', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )

    def test_requiert_authentification(self):
        response = self.client.get(reverse('espace_pro_dashboard'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('espace_pro_dashboard')}")

    def test_particulier_est_redirige_hors_espace_pro(self):
        self.client.force_login(self.particulier)
        response = self.client.get(reverse('espace_pro_dashboard'))
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))

    def test_pro_accede_au_dashboard(self):
        self.client.force_login(self.pro)
        response = self.client.get(reverse('espace_pro_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_tableau_de_bord_vendeur_redirige_le_pro_actif(self):
        self.client.force_login(self.pro)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertRedirects(response, reverse('espace_pro_dashboard'))

    def test_pro_en_attente_ne_redirige_pas_vers_espace_pro(self):
        self.pro.statut_compte = Utilisateur.StatutCompte.EN_ATTENTE
        self.pro.save()
        self.client.force_login(self.pro)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'espace-pro', status_code=200)


class MembreEquipeTest(TestCase):
    def setUp(self):
        self.pro = creer_pro()
        self.client.force_login(self.pro)

    def membre_data(self, **overrides):
        data = {
            'prenom': 'Jean', 'nom': 'Kouassi', 'email': 'jean@exemple.ci',
            'telephone': '0708091011', 'role': MembreEquipe.Role.GESTIONNAIRE, 'password': 'MotDePasseMembre1',
        }
        data.update(overrides)
        return data

    def test_titulaire_peut_inviter_un_membre(self):
        response = self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data())
        self.assertRedirects(response, reverse('espace_pro_equipe'))
        membre = MembreEquipe.objects.get(compte_pro=self.pro)
        self.assertEqual(membre.membre.email, 'jean@exemple.ci')
        self.assertEqual(membre.membre.type_compte, Utilisateur.TypeCompte.PARTICULIER)
        self.assertTrue(membre.actif)

    def test_email_deja_utilise_est_refuse(self):
        response = self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data(email=self.pro.email))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MembreEquipe.objects.filter(compte_pro=self.pro).exists())

    def test_membre_peut_se_connecter_et_gerer_le_stock_du_titulaire(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data())
        membre = MembreEquipe.objects.get(compte_pro=self.pro).membre

        self.client.force_login(membre)
        response = self.client.get(reverse('mes_annonces'))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('annonce_creer'), {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 8500000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état.', 'action': 'enregistrer',
        })
        self.assertRedirects(response, reverse('mes_annonces'))
        self.assertEqual(Annonce.objects.get().vendeur, self.pro)

    def test_membre_lecture_seule_ne_peut_pas_creer_dannonce(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data(
            email='lecteur@exemple.ci', role=MembreEquipe.Role.LECTURE_SEULE,
        ))
        membre = MembreEquipe.objects.get(compte_pro=self.pro).membre
        self.client.force_login(membre)

        response = self.client.post(reverse('annonce_creer'), {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 8500000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état.', 'action': 'enregistrer',
        })
        self.assertRedirects(response, reverse('mes_annonces'))
        self.assertFalse(Annonce.objects.exists())

    def test_membre_ne_peut_pas_inviter_dautres_membres(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data())
        membre = MembreEquipe.objects.get(compte_pro=self.pro).membre
        self.client.force_login(membre)

        response = self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data(email='autre@exemple.ci'))
        self.assertRedirects(response, reverse('espace_pro_equipe'))
        self.assertEqual(MembreEquipe.objects.filter(compte_pro=self.pro).count(), 1)

    def test_suspendre_puis_reactiver_un_membre(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data())
        membre_equipe = MembreEquipe.objects.get(compte_pro=self.pro)

        response = self.client.post(reverse('espace_pro_equipe_toggle', args=[membre_equipe.pk]))
        self.assertRedirects(response, reverse('espace_pro_equipe'))
        membre_equipe.refresh_from_db()
        self.assertFalse(membre_equipe.actif)

        self.client.post(reverse('espace_pro_equipe_toggle', args=[membre_equipe.pk]))
        membre_equipe.refresh_from_db()
        self.assertTrue(membre_equipe.actif)

    def test_membre_suspendu_perd_lacces_au_stock_du_titulaire(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data())
        membre_equipe = MembreEquipe.objects.get(compte_pro=self.pro)
        self.client.post(reverse('espace_pro_equipe_toggle', args=[membre_equipe.pk]))

        self.client.force_login(membre_equipe.membre)
        response = self.client.get(reverse('espace_pro_dashboard'))
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))

    def test_retirer_un_membre_ne_supprime_pas_son_compte(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), self.membre_data())
        membre_equipe = MembreEquipe.objects.get(compte_pro=self.pro)
        membre_pk = membre_equipe.membre.pk

        response = self.client.post(reverse('espace_pro_equipe_retirer', args=[membre_equipe.pk]))
        self.assertRedirects(response, reverse('espace_pro_equipe'))
        self.assertFalse(MembreEquipe.objects.filter(pk=membre_equipe.pk).exists())
        self.assertTrue(Utilisateur.objects.filter(pk=membre_pk).exists())


class ProspectTest(TestCase):
    def setUp(self):
        self.pro = creer_pro()
        self.client.force_login(self.pro)
        self.annonce = Annonce.objects.create(
            vendeur=self.pro, marque='Toyota', modele='Corolla', annee=2019, prix=8500000,
            kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Gris', description='Très bon état.',
        )

    def test_creer_un_prospect(self):
        response = self.client.post(reverse('espace_pro_prospect_creer'), {
            'nom': 'Bakary', 'telephone': '0708091011', 'annonce': self.annonce.pk,
        })
        self.assertRedirects(response, reverse('espace_pro_prospects'))
        prospect = Prospect.objects.get(compte_pro=self.pro)
        self.assertEqual(prospect.statut, Prospect.Statut.NOUVEAU)
        self.assertEqual(prospect.annonce, self.annonce)

    def test_sans_telephone_ni_email_est_refuse(self):
        response = self.client.post(reverse('espace_pro_prospect_creer'), {'nom': 'Bakary'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Prospect.objects.exists())

    def test_changer_le_statut_dun_prospect(self):
        prospect = Prospect.objects.create(compte_pro=self.pro, nom='Bakary', telephone='0708091011')
        response = self.client.post(reverse('espace_pro_prospect_statut', args=[prospect.pk]), {
            'statut': Prospect.Statut.CONTACTE, 'notes': 'Rappelé le matin.',
        })
        self.assertRedirects(response, reverse('espace_pro_prospects'))
        prospect.refresh_from_db()
        self.assertEqual(prospect.statut, Prospect.Statut.CONTACTE)
        self.assertEqual(prospect.notes, 'Rappelé le matin.')

    def test_supprimer_un_prospect(self):
        prospect = Prospect.objects.create(compte_pro=self.pro, nom='Bakary', telephone='0708091011')
        response = self.client.post(reverse('espace_pro_prospect_supprimer', args=[prospect.pk]))
        self.assertRedirects(response, reverse('espace_pro_prospects'))
        self.assertFalse(Prospect.objects.filter(pk=prospect.pk).exists())

    def test_prospect_dun_autre_titulaire_est_invisible(self):
        autre_pro = creer_pro(email='autre-pro@exemple.ci')
        prospect_autre = Prospect.objects.create(compte_pro=autre_pro, nom='Fatim', telephone='0708091012')
        response = self.client.post(reverse('espace_pro_prospect_statut', args=[prospect_autre.pk]), {
            'statut': Prospect.Statut.CONTACTE,
        })
        self.assertEqual(response.status_code, 404)

    def test_lecture_seule_ne_peut_pas_ajouter_de_prospect(self):
        self.client.post(reverse('espace_pro_equipe_inviter'), {
            'prenom': 'Jean', 'nom': 'Kouassi', 'email': 'lecteur@exemple.ci',
            'telephone': '0708091011', 'role': MembreEquipe.Role.LECTURE_SEULE, 'password': 'MotDePasseMembre1',
        })
        membre = MembreEquipe.objects.get(compte_pro=self.pro).membre
        self.client.force_login(membre)

        response = self.client.post(reverse('espace_pro_prospect_creer'), {'nom': 'Bakary', 'telephone': '0708091011'})
        self.assertRedirects(response, reverse('espace_pro_prospects'))
        self.assertFalse(Prospect.objects.exists())

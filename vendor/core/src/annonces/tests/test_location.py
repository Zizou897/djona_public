from django.test import TestCase
from django.urls import reverse

from annonces.forms import AnnonceForm
from annonces.models import Annonce
from app.models import Utilisateur


def donnees(**surcharge):
    data = {
        'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'kilometrage': 45000,
        'carburant': Annonce.Carburant.ESSENCE, 'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE,
        'couleur': 'Gris', 'etat': Annonce.Etat.OCCASION, 'ville': 'abidjan_cocody', 'description': 'Très bon état.',
    }
    data.update(surcharge)
    return data


class FormulaireLocationTest(TestCase):
    def test_vente_exige_le_prix_et_ignore_les_champs_de_location(self):
        form = AnnonceForm(donnees(type_annonce='vente', prix_jour='30000', caution='100000'))
        self.assertFalse(form.is_valid())
        self.assertIn('prix', form.errors)

        form = AnnonceForm(donnees(type_annonce='vente', prix='8500000', prix_jour='30000', caution='100000'))
        self.assertTrue(form.is_valid(), form.errors)
        annonce = form.save(commit=False)
        self.assertEqual((annonce.prix, annonce.prix_jour, annonce.caution), (8500000, None, None))

    def test_type_absent_vaut_vente(self):
        form = AnnonceForm(donnees(prix='5000000'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).type_annonce, 'vente')

    def test_location_exige_au_moins_un_tarif(self):
        form = AnnonceForm(donnees(type_annonce='location', caution='200000'))
        self.assertFalse(form.is_valid())
        self.assertIn('prix_jour', form.errors)
        self.assertNotIn('prix', form.errors)  # le prix de vente n'est pas demandé

    def test_location_accepte_une_seule_periode_au_choix(self):
        for champ in ('prix_jour', 'prix_semaine', 'prix_mois'):
            form = AnnonceForm(donnees(type_annonce='location', **{champ: '45000'}))
            self.assertTrue(form.is_valid(), (champ, form.errors))
            annonce = form.save(commit=False)
            self.assertEqual(annonce.prix, 0)
            self.assertEqual([p for p, _ in annonce.tarifs_location], [champ.replace('prix_', '')])
            self.assertIsNone(annonce.caution)

    def test_tarif_a_zero_est_refuse(self):
        form = AnnonceForm(donnees(type_annonce='location', prix_jour='0', prix_mois='600000'))
        self.assertFalse(form.is_valid())
        self.assertIn('prix_jour', form.errors)

    def test_resume_prix(self):
        vente = Annonce(prix=8500000)
        self.assertIn('8', vente.resume_prix)
        self.assertTrue(vente.resume_prix.endswith('FCFA'))
        location = Annonce(type_annonce='location', prix=0, prix_semaine=200000, prix_mois=750000)
        self.assertTrue(location.resume_prix.endswith('FCFA / semaine'))
        self.assertEqual(Annonce(type_annonce='location', prix=0).resume_prix, 'Tarif non renseigné')


class CreationLocationVueTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='loc@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def test_brouillon_de_location_enregistre_les_tarifs_et_la_caution(self):
        reponse = self.client.post(reverse('annonce_creer'), {
            **donnees(), 'type_annonce': 'location', 'prix_jour': '35000', 'prix_mois': '750000',
            'caution': '300000', 'action': 'enregistrer',
        })
        self.assertRedirects(reponse, reverse('mes_annonces'))
        annonce = Annonce.objects.get()
        self.assertTrue(annonce.est_location)
        self.assertEqual((annonce.prix, annonce.prix_jour, annonce.prix_semaine, annonce.prix_mois, annonce.caution),
                         (0, 35000, None, 750000, 300000))
        page = self.client.get(reverse('mes_annonces')).content.decode()
        self.assertIn('/ jour', page)

    def test_formulaire_affiche_le_choix_vente_ou_location(self):
        page = self.client.get(reverse('annonce_creer')).content.decode()
        for attendu in ('À vendre', 'À louer', 'Tarif par jour', 'Tarif par semaine', 'Tarif par mois', 'Caution'):
            self.assertIn(attendu, page)

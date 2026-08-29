from django.test import TestCase

from app.models import Utilisateur
from annonces.models import Annonce, AnnoncePhoto


class AnnonceModelTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405',
        )

    def annonce_data(self, **overrides):
        data = {
            'vendeur': self.vendeur,
            'marque': 'Toyota',
            'modele': 'Corolla',
            'annee': 2019,
            'prix': 8500000,
            'kilometrage': 45000,
            'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE,
            'couleur': 'Gris',
            'description': 'Très bon état, entretien à jour.',
        }
        data.update(overrides)
        return data

    def test_statut_par_defaut_est_brouillon(self):
        annonce = Annonce.objects.create(**self.annonce_data())
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertFalse(annonce.publish)

    def test_publish_se_synchronise_avec_statut_publiee(self):
        annonce = Annonce.objects.create(**self.annonce_data(statut=Annonce.Statut.PUBLIEE))
        self.assertTrue(annonce.publish)
        annonce.statut = Annonce.Statut.REFUSEE
        annonce.save()
        self.assertFalse(annonce.publish)

    def test_suppression_du_vendeur_supprime_ses_annonces(self):
        annonce = Annonce.objects.create(**self.annonce_data())
        annonce_pk = annonce.pk
        self.vendeur.delete()
        self.assertFalse(Annonce.objects.filter(pk=annonce_pk).exists())

    def test_photo_ordonnee_par_ordre(self):
        annonce = Annonce.objects.create(**self.annonce_data())
        AnnoncePhoto.objects.create(annonce=annonce, image='annonces/test2.jpg', ordre=1)
        AnnoncePhoto.objects.create(annonce=annonce, image='annonces/test1.jpg', ordre=0)
        photos = list(annonce.photos.all())
        self.assertEqual(photos[0].ordre, 0)
        self.assertEqual(photos[1].ordre, 1)

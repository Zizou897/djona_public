import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from annonces.models import Annonce, AnnoncePhoto
from app.models import Profil, Utilisateur


def grosse_photo(taille=(3200, 2000)):
    """JPEG bruité d'environ la taille d'une photo de téléphone."""
    image = Image.frombytes('RGB', taille, os.urandom(taille[0] * taille[1] * 3))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=92)
    return buffer.getvalue()


class ConversionPhotosTest(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        self.annonce = Annonce.objects.create(
            vendeur=vendeur, marque='Toyota', modele='Corolla', annee=2019, prix=8500000, kilometrage=45000,
            carburant=Annonce.Carburant.ESSENCE, boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE,
            couleur='Gris', description='Très bon état.',
        )

    def test_photo_televersee_est_stockee_en_webp_reduite(self):
        with override_settings(MEDIA_ROOT=self.media):
            brut = grosse_photo()
            photo = AnnoncePhoto.objects.create(
                annonce=self.annonce, ordre=0,
                image=SimpleUploadedFile('IMG_2041.JPG', brut, content_type='image/jpeg'),
            )
            self.assertTrue(photo.image.name.endswith('.webp'), photo.image.name)
            with Image.open(photo.image.path) as stockee:
                self.assertEqual(stockee.format, 'WEBP')
                self.assertEqual(stockee.width, 1600)
            self.assertLess(photo.image.size, len(brut))

    def test_avatar_est_stocke_en_webp_pour_un_logo(self):
        with override_settings(MEDIA_ROOT=self.media):
            profil = Profil.objects.create(user=self.annonce.vendeur)
            profil.avatar = SimpleUploadedFile('logo.jpg', grosse_photo((1400, 900)), content_type='image/jpeg')
            profil.save()
            self.assertTrue(profil.avatar.name.endswith('.webp'))
            with Image.open(profil.avatar.path) as stockee:
                self.assertEqual(stockee.width, 600)

    def test_photo_deja_enregistree_n_est_pas_retraitee(self):
        photo = AnnoncePhoto.objects.create(annonce=self.annonce, image='annonces/ancienne.jpg', ordre=0)
        photo.ordre = 1
        photo.save()
        self.assertEqual(photo.image.name, 'annonces/ancienne.jpg')

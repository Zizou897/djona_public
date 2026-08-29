from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from annonces.forms import AnnonceForm
from annonces.models import Annonce

# Le plus petit PNG valide possible (1x1 pixel transparent), en octets bruts —
# nécessaire pour que la validation Pillow (forms.ImageField().clean()) accepte le
# fichier comme une vraie image.
PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00'
    b'\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class AnnonceFormTest(TestCase):
    def valid_data(self, **overrides):
        data = {
            'marque': 'Toyota',
            'modele': 'Corolla',
            'annee': 2019,
            'prix': 8500000,
            'kilometrage': 45000,
            'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE,
            'couleur': 'Gris',
            'description': 'Très bon état.',
        }
        data.update(overrides)
        return data

    def test_valide_sans_photo(self):
        form = AnnonceForm(data=self.valid_data(), files=MultiValueDict())
        self.assertTrue(form.is_valid(), form.errors)

    def test_valide_avec_photos(self):
        photo = SimpleUploadedFile('photo.png', PNG_1PX, content_type='image/png')
        files = MultiValueDict({'photos': [photo]})
        form = AnnonceForm(data=self.valid_data(), files=files)
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejette_plus_de_8_photos(self):
        photos = [
            SimpleUploadedFile(f'photo{i}.png', PNG_1PX, content_type='image/png')
            for i in range(9)
        ]
        files = MultiValueDict({'photos': photos})
        form = AnnonceForm(data=self.valid_data(), files=files)
        self.assertFalse(form.is_valid())

    def test_rejette_fichier_non_image(self):
        fichier = SimpleUploadedFile('doc.txt', b'pas une image', content_type='text/plain')
        files = MultiValueDict({'photos': [fichier]})
        form = AnnonceForm(data=self.valid_data(), files=files)
        self.assertFalse(form.is_valid())

    def test_ne_contient_pas_de_champ_vendeur(self):
        form = AnnonceForm()
        self.assertNotIn('vendeur', form.fields)

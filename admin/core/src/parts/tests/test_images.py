import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from moderation.models import AnnonceMirror, AnnoncePhotoMirror, CompteVendeur
from parts.models import PartCategoryMirror, PartImageMirror, PartMirror

DB = 'public_db'


def grosse_photo(taille=(3200, 2000)):
    image = Image.frombytes('RGB', taille, os.urandom(taille[0] * taille[1] * 3))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=92)
    return buffer.getvalue()


class ConversionImagesAdminTest(TestCase):
    databases = {'default', 'vendor_db', DB}

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def test_photo_de_piece_est_stockee_en_webp(self):
        category = PartCategoryMirror.objects.using(DB).create(name='Catégorie images', order=98)
        part = PartMirror.objects.using(DB).create(reference='IMG-1', name='Disque', category=category)
        try:
            with override_settings(MEDIA_ROOT=self.media):
                image = PartImageMirror(part=part, image=SimpleUploadedFile('p.jpg', grosse_photo(), content_type='image/jpeg'))
                image.save(using=DB)
                self.assertTrue(image.image.name.endswith('.webp'), image.image.name)
                with Image.open(image.image.path) as stored:
                    self.assertEqual((stored.format, stored.width), ('WEBP', 1600))
        finally:
            PartImageMirror.objects.using(DB).filter(part=part).delete()
            part.delete(using=DB)
            category.delete(using=DB)

    def test_photo_d_annonce_creee_par_le_staff_est_stockee_en_webp(self):
        vendeur = CompteVendeur.objects.using('vendor_db').create(
            email='img-staff@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )
        annonce = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=vendeur, marque='Toyota', modele='Corolla', annee=2019, prix=8500000, kilometrage=45000,
            carburant='essence', boite_vitesses='automatique', couleur='Gris', description='Test',
            statut=AnnonceMirror.Statut.EN_ATTENTE, created_at='2026-08-27T10:00:00Z', update_at='2026-08-27T10:00:00Z',
        )
        try:
            with override_settings(MEDIA_ROOT=self.media):
                photo = AnnoncePhotoMirror.objects.using('vendor_db').create(
                    annonce=annonce, ordre=0,
                    image=SimpleUploadedFile('IMG_9.jpeg', grosse_photo(), content_type='image/jpeg'),
                )
                self.assertTrue(photo.image.name.endswith('.webp'), photo.image.name)
        finally:
            AnnoncePhotoMirror.objects.using('vendor_db').filter(annonce_id=annonce.pk).delete()
            AnnonceMirror.objects.using('vendor_db').filter(pk=annonce.pk).delete()
            CompteVendeur.objects.using('vendor_db').filter(pk=vendeur.pk).delete()

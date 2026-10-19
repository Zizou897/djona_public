import io
import os
import shutil
import tempfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from apps.catalog.models import Vehicle, VehicleImage
from apps.core.imaging import convert_path, optimize_field, optimize_upload
from apps.core.models import Partner
from apps.parts.models import PartRequest


def photo_bytes(size=(3000, 2000), fmt='JPEG', quality=95):
    """Image bruitée (≈ photo) pour que la compression ait quelque chose à gagner."""
    image = Image.frombytes('RGB', size, os.urandom(size[0] * size[1] * 3))
    buffer = io.BytesIO()
    image.save(buffer, fmt, quality=quality)
    return buffer.getvalue()


class OptimizeUploadTests(TestCase):
    def test_large_jpeg_becomes_resized_webp(self):
        upload = SimpleUploadedFile('IMG 001.jpg', photo_bytes(), content_type='image/jpeg')
        result = optimize_upload(upload)
        self.assertEqual(result.name, 'IMG 001.webp')
        with Image.open(io.BytesIO(result.read())) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(image.width, 1600)
            self.assertEqual(image.height, round(2000 * 1600 / 3000))
        self.assertLess(result.size, upload.size)

    def test_small_image_is_not_upscaled(self):
        upload = SimpleUploadedFile('a.png', photo_bytes((400, 300), 'PNG'), content_type='image/png')
        result = optimize_upload(upload)
        with Image.open(io.BytesIO(result.read())) as image:
            self.assertEqual(image.size, (400, 300))

    def test_unreadable_file_is_returned_untouched(self):
        upload = SimpleUploadedFile('faux.jpg', b'pas une image', content_type='image/jpeg')
        self.assertIs(optimize_upload(upload), upload)

    def test_animated_gif_and_small_webp_are_untouched(self):
        frames = [Image.new('RGB', (30, 30), c).convert('P') for c in ('red', 'blue')]
        buffer = io.BytesIO()
        frames[0].save(buffer, 'GIF', save_all=True, append_images=frames[1:], duration=100, loop=0)
        gif = SimpleUploadedFile('anim.gif', buffer.getvalue(), content_type='image/gif')
        self.assertIs(optimize_upload(gif), gif)
        webp_buffer = io.BytesIO()
        Image.new('RGB', (200, 100), 'white').save(webp_buffer, 'WEBP')
        webp = SimpleUploadedFile('a.webp', webp_buffer.getvalue(), content_type='image/webp')
        self.assertIs(optimize_upload(webp), webp)

    def test_transparency_is_preserved(self):
        buffer = io.BytesIO()
        Image.new('RGBA', (900, 300), (255, 0, 0, 0)).save(buffer, 'PNG')
        result = optimize_upload(SimpleUploadedFile('logo.png', buffer.getvalue()), max_width=600)
        with Image.open(io.BytesIO(result.read())) as image:
            self.assertIn('A', image.getbands())
            self.assertEqual(image.width, 600)

    def test_optimize_field_ignores_saved_files(self):
        class Committed:
            _committed = True
            name = 'x.jpg'
        committed = Committed()
        self.assertIs(optimize_field(committed), committed)
        self.assertFalse(optimize_field(None))


class StorageTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def test_part_request_photo_is_stored_as_webp(self):
        with override_settings(MEDIA_ROOT=self.media):
            request = PartRequest.objects.create(
                full_name='Jean', phone='+225 0700000000', make='Toyota', model='Corolla', year=2015,
                part_name='Amortisseur', description='Bruit à gauche',
                photo=SimpleUploadedFile('photo.jpg', photo_bytes(), content_type='image/jpeg'),
            )
            self.assertTrue(request.photo.name.endswith('.webp'), request.photo.name)
            self.assertTrue(Path(self.media, request.photo.name).exists())
            with Image.open(Path(self.media, request.photo.name)) as stored:
                self.assertEqual(stored.width, 1600)

    def test_convert_path_writes_webp_or_copies_original(self):
        source = Path(self.media) / 'src.jpg'
        source.write_bytes(photo_bytes((2000, 1000)))
        out = convert_path(source, Path(self.media) / 'out')
        self.assertEqual(out.name, 'src.webp')
        broken = Path(self.media) / 'broken.jpg'
        broken.write_bytes(b'xxx')
        self.assertEqual(convert_path(broken, Path(self.media) / 'out').name, 'broken.jpg')

    def test_management_command_converts_existing_vehicle_images(self):
        with override_settings(MEDIA_ROOT=self.media):
            folder = Path(self.media, 'vehicles', 'annonce-1')
            folder.mkdir(parents=True)
            (folder / 'old.jpg').write_bytes(photo_bytes((2400, 1200)))
            vehicle = Vehicle.objects.create(
                brand='Toyota', model_name='Corolla', year=2018, price=5_000_000, mileage=50_000,
            )
            image = VehicleImage.objects.create(vehicle=vehicle, image='vehicles/annonce-1/old.jpg', order=0)

            call_command('optimize_media_images', '--dry-run', stdout=io.StringIO())
            image.refresh_from_db()
            self.assertEqual(image.image.name, 'vehicles/annonce-1/old.jpg')
            self.assertTrue((folder / 'old.jpg').exists())

            out = io.StringIO()
            call_command('optimize_media_images', stdout=out)
            image.refresh_from_db()
            self.assertEqual(image.image.name, 'vehicles/annonce-1/old.webp')
            self.assertTrue((folder / 'old.webp').exists())
            self.assertFalse((folder / 'old.jpg').exists())
            self.assertIn('1 converti', out.getvalue())

            again = io.StringIO()
            call_command('optimize_media_images', stdout=again)
            self.assertIn('Rien à convertir', again.getvalue())


class SyncPhotosTests(TestCase):
    """_sync_photos copie les photos vendeur en WebP et reste idempotent."""

    def setUp(self):
        self.media = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.vendor_media = self.media / 'vendor'
        (self.vendor_media / 'annonces' / '2026' / '10').mkdir(parents=True)
        (self.vendor_media / 'annonces' / '2026' / '10' / 'a.jpg').write_bytes(photo_bytes((2400, 1200)))
        self.vehicle = Vehicle.objects.create(brand='Kia', model_name='Rio', year=2018, price=4_000_000, mileage=60_000)

    def run_sync(self, photos):
        from types import SimpleNamespace
        from unittest import mock

        from apps.vendor_sync.management.commands import sync_validated_annonces as module

        fake = mock.MagicMock()
        fake.objects.using.return_value.filter.return_value.order_by.return_value = photos
        with override_settings(MEDIA_ROOT=str(self.media / 'public')), \
                mock.patch.object(module, 'AnnoncePhotoMirror', fake), \
                mock.patch.object(module, 'VENDOR_MEDIA_ROOT', str(self.vendor_media)):
            return module.Command()._sync_photos(SimpleNamespace(id=5), self.vehicle)

    def photo(self, name):
        from types import SimpleNamespace
        return SimpleNamespace(image=SimpleNamespace(name=name), ordre=0)

    def test_photo_is_copied_as_webp_once(self):
        photos = [self.photo('annonces/2026/10/a.jpg')]
        self.assertEqual(self.run_sync(photos), 1)
        image = self.vehicle.images.get()
        self.assertEqual(image.image.name, 'vehicles/annonce-5/a.webp')
        self.assertTrue((self.media / 'public' / 'vehicles' / 'annonce-5' / 'a.webp').exists())
        self.assertEqual(self.run_sync(photos), 0)
        self.assertEqual(self.vehicle.images.count(), 1)

    def test_legacy_jpg_already_synced_is_not_duplicated(self):
        VehicleImage.objects.create(vehicle=self.vehicle, image='vehicles/annonce-5/a.jpg', order=0)
        self.assertEqual(self.run_sync([self.photo('annonces/2026/10/a.jpg')]), 0)
        self.assertEqual(self.vehicle.images.count(), 1)


class LowQualityJpegTests(TestCase):
    def test_already_compressed_jpeg_still_becomes_smaller_webp(self):
        """Un JPEG très compressé donnerait un WebP q82 plus lourd : on retente plus bas."""
        image = Image.new('RGB', (1200, 700))
        image.putdata([((x * 3) % 256, (y * 5) % 256, ((x + y) * 2) % 256) for y in range(700) for x in range(1200)])
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=35)
        upload = SimpleUploadedFile('a.jpg', buffer.getvalue(), content_type='image/jpeg')
        result = optimize_upload(upload)
        self.assertTrue(result.name.endswith('.webp'))
        self.assertLess(result.size, len(buffer.getvalue()))

import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from parts.models import (PartCategoryMirror, PartCompatibilityMirror, PartImageMirror, PartMirror,
                          PartRequestMirror)

User = get_user_model()
DB = 'public_db'


def png_upload(name='piece.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class PartsBase(TestCase):
    databases = {'default', DB}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-parts', password='motdepasse', is_staff=True)
        self.category = PartCategoryMirror.objects.using(DB).create(name='Catégorie test', icon='build', order=99)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def tearDown(self):
        PartRequestMirror.objects.using(DB).all().delete()
        PartImageMirror.objects.using(DB).all().delete()
        PartCompatibilityMirror.objects.using(DB).all().delete()
        PartMirror.objects.using(DB).all().delete()
        PartCategoryMirror.objects.using(DB).filter(pk=self.category.pk).delete()

    def make_part(self, **overrides):
        data = dict(reference='T-001', name='Plaquettes', category=self.category)
        data.update(overrides)
        return PartMirror.objects.using(DB).create(**data)


class AccessTests(PartsBase):
    def test_all_pages_require_staff(self):
        for name in ('part_liste', 'part_creer', 'part_import', 'part_import_modele', 'part_categorie_liste',
                     'part_demande_liste'):
            url = reverse(name)
            self.assertRedirects(self.client.get(url), f"{reverse('connexion_admin')}?next={url}",
                                 msg_prefix=name)


class CatalogTests(PartsBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def payload(self, **overrides):
        data = {
            'reference': 'DJP-100', 'name': 'Filtre à air', 'category': self.category.pk,
            'manufacturer_reference': '17801-0H010', 'brand': 'Denso', 'condition': '', 'price': '',
            'availability': 'a_confirmer', 'warranty': '', 'lead_time': '', 'description': '',
            'compatibilities': 'Toyota / Corolla / 2014 / 2019\nPeugeot', 'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_create_part_keeps_unknown_fields_empty(self):
        with override_settings(MEDIA_ROOT=self.media):
            response = self.client.post(reverse('part_creer'), self.payload(photos=[png_upload(f'p{i}.png') for i in range(3)]))
        self.assertRedirects(response, reverse('part_liste'))
        part = PartMirror.objects.using(DB).get(reference='DJP-100')
        self.assertEqual(part.condition, '')
        self.assertIsNone(part.price)
        self.assertEqual(part.availability, 'a_confirmer')
        self.assertTrue(part.is_active)
        self.assertFalse(part.is_featured)
        compat = list(part.compatibilities.using(DB).values_list('make', 'model', 'year_from', 'year_to'))
        self.assertEqual(sorted(compat), [('Peugeot', '', None, None), ('Toyota', 'Corolla', 2014, 2019)])
        self.assertEqual(part.images.using(DB).count(), 3)

    def test_duplicate_reference_and_bad_compatibility_are_rejected(self):
        self.make_part(reference='DJP-100')
        response = self.client.post(reverse('part_creer'), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertIn('reference', response.context['form'].errors)
        response = self.client.post(reverse('part_creer'), self.payload(reference='DJP-101', compatibilities='Toyota / Corolla / 2020 / 2010'))
        self.assertIn('compatibilities', response.context['form'].errors)
        self.assertFalse(PartMirror.objects.using(DB).filter(reference='DJP-101').exists())

    def test_invalid_photo_blocks_save(self):
        bad = SimpleUploadedFile('faux.png', b'pas une image', content_type='image/png')
        with override_settings(MEDIA_ROOT=self.media):
            response = self.client.post(reverse('part_creer'), self.payload(photos=[bad, png_upload('b.png'), png_upload('c.png')]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pas une image valide')
        self.assertFalse(PartMirror.objects.using(DB).filter(reference='DJP-100').exists())

    def test_update_replaces_compatibilities_and_can_remove_photo(self):
        part = self.make_part()
        PartCompatibilityMirror.objects.using(DB).create(part=part, make='Kia')
        with override_settings(MEDIA_ROOT=self.media):
            image = PartImageMirror(part=part, image=png_upload(), order=0)
            image.save(using=DB)
            response = self.client.post(reverse('part_modifier', args=[part.pk]), self.payload(
                reference='T-001', name='Plaquettes v2', compatibilities='Hyundai / Accent',
                supprimer_photos=[str(image.pk)],
            ))
        self.assertRedirects(response, reverse('part_liste'))
        part.refresh_from_db(using=DB)
        self.assertEqual(part.name, 'Plaquettes v2')
        self.assertEqual(list(part.compatibilities.using(DB).values_list('make', flat=True)), ['Hyundai'])
        self.assertEqual(part.images.using(DB).count(), 0)

    def test_edit_page_shows_existing_compatibilities(self):
        part = self.make_part()
        PartCompatibilityMirror.objects.using(DB).create(part=part, make='Toyota', model='Yaris', year_from=2012, year_to=2018)
        response = self.client.get(reverse('part_modifier', args=[part.pk]))
        self.assertContains(response, 'Toyota / Yaris / 2012 / 2018')

    def test_toggle_and_delete(self):
        part = self.make_part()
        self.client.post(reverse('part_basculer', args=[part.pk]))
        part.refresh_from_db(using=DB)
        self.assertFalse(part.is_active)
        self.assertEqual(self.client.get(reverse('part_basculer', args=[part.pk])).status_code, 405)
        self.client.post(reverse('part_supprimer', args=[part.pk]))
        self.assertFalse(PartMirror.objects.using(DB).filter(pk=part.pk).exists())

    def test_list_filters(self):
        self.make_part()
        self.make_part(reference='T-002', name='Disque', is_active=False)
        response = self.client.get(reverse('part_liste'), {'visibilite': 'masquees'})
        self.assertContains(response, 'Disque')
        self.assertNotContains(response, 'Plaquettes')
        response = self.client.get(reverse('part_liste'), {'q': 'T-001'})
        self.assertContains(response, 'Plaquettes')


class CategoryTests(PartsBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_add_rename_and_toggle(self):
        self.client.post(reverse('part_categorie_liste'), {'name': 'Pneumatiques', 'icon': 'tire_repair', 'order': 20})
        created = PartCategoryMirror.objects.using(DB).get(name='Pneumatiques')
        self.client.post(reverse('part_categorie_modifier', args=[created.pk]), {'name': 'Pneus', 'icon': 'tire_repair', 'order': 21})
        created.refresh_from_db(using=DB)
        self.assertEqual((created.name, created.order), ('Pneus', 21))
        self.client.post(reverse('part_categorie_basculer', args=[created.pk]))
        created.refresh_from_db(using=DB)
        self.assertFalse(created.is_active)
        PartCategoryMirror.objects.using(DB).filter(pk=created.pk).delete()

    def test_duplicate_category_rejected(self):
        response = self.client.post(reverse('part_categorie_liste'), {'name': 'catégorie TEST', 'icon': 'build', 'order': 1})
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['form'].errors)


class RequestTests(PartsBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.demande = PartRequestMirror.objects.using(DB).create(
            reference='DJ-PC-2026-9999', full_name='Jean Kouadio', phone='+225 0700000000', make='Toyota',
            model='Corolla', year=2015, part_name='Amortisseur', description='Bruit à gauche', created_at=timezone.now(),
        )

    def test_list_detail_and_follow_up(self):
        self.assertContains(self.client.get(reverse('part_demande_liste')), 'DJ-PC-2026-9999')
        self.assertNotContains(self.client.get(reverse('part_demande_liste'), {'statut': 'acceptee'}), 'DJ-PC-2026-9999')
        url = reverse('part_demande_detail', args=[self.demande.pk])
        self.assertContains(self.client.get(url), 'Amortisseur')
        response = self.client.post(url, {'status': 'proposition_envoyee', 'proposed_price': '35000',
                                          'proposed_lead_time': '3 jours', 'internal_note': 'IAS a confirmé.'})
        self.assertRedirects(response, url)
        self.demande.refresh_from_db(using=DB)
        self.assertEqual(self.demande.status, 'proposition_envoyee')
        self.assertEqual(self.demande.proposed_price, 35000)
        self.assertEqual(self.demande.internal_note, 'IAS a confirmé.')

    def test_invalid_status_is_rejected(self):
        url = reverse('part_demande_detail', args=[self.demande.pk])
        self.client.post(url, {'status': 'nimporte', 'proposed_price': '', 'proposed_lead_time': '', 'internal_note': ''})
        self.demande.refresh_from_db(using=DB)
        self.assertEqual(self.demande.status, 'nouvelle')

    def test_counter_exposes_new_requests(self):
        response = self.client.get(reverse('compteurs_admin'))
        self.assertGreaterEqual(response.json().get('pieces', 0), 1)


class InterestRequestTests(PartsBase):
    """Les « Je suis intéressé » arrivent dans les demandes de pièces, distincts des pièces introuvables."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.part = self.make_part()
        self.interest = PartRequestMirror.objects.using(DB).create(
            reference='DJ-PC-2026-9001', request_type='interesse', full_name='Awa Traoré', phone='+225 0701020304',
            part=self.part, part_name='Plaquettes', part_reference='T-001', description='', created_at=timezone.now(),
        )
        self.search = PartRequestMirror.objects.using(DB).create(
            reference='DJ-PC-2026-9002', request_type='introuvable', full_name='Jean Kouadio', phone='+225 0700000000',
            make='Toyota', model='Corolla', year=2015, part_name='Amortisseur', description='Bruit à gauche',
            created_at=timezone.now(),
        )

    def test_list_shows_both_kinds_with_badges_and_filters_by_type(self):
        html = self.client.get(reverse('part_demande_liste')).content.decode()
        self.assertIn('DJ-PC-2026-9001', html)
        self.assertIn('DJ-PC-2026-9002', html)
        self.assertIn('Intéressé par une pièce', html)
        self.assertIn('Pièce introuvable', html)
        self.assertIn('à rappeler', html)  # intérêt sans message
        only_interest = self.client.get(reverse('part_demande_liste'), {'type': 'interesse'}).content.decode()
        self.assertIn('DJ-PC-2026-9001', only_interest)
        self.assertNotIn('DJ-PC-2026-9002', only_interest)
        only_search = self.client.get(reverse('part_demande_liste'), {'type': 'introuvable'}).content.decode()
        self.assertIn('DJ-PC-2026-9002', only_search)
        self.assertNotIn('DJ-PC-2026-9001', only_search)

    def test_interest_detail_handles_missing_vehicle_and_links_the_part(self):
        response = self.client.get(reverse('part_demande_detail', args=[self.interest.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Intéressé par une pièce', html)
        self.assertIn('Non précisée', html)
        self.assertNotIn('None', html.split('Véhicule')[-1][:600])
        self.assertIn(reverse('part_modifier', args=[self.part.pk]), html)

    def test_interest_counts_in_the_new_requests_counter_and_can_be_followed_up(self):
        counters = self.client.get(reverse('compteurs_admin')).json()
        self.assertGreaterEqual(counters.get('pieces', 0), 2)
        url = reverse('part_demande_detail', args=[self.interest.pk])
        self.client.post(url, {'status': 'en_recherche', 'proposed_price': '', 'proposed_lead_time': '', 'internal_note': 'Rappelé.'})
        self.interest.refresh_from_db(using=DB)
        self.assertEqual(self.interest.status, 'en_recherche')


class PhotoRulesLikeVehiclesTests(PartsBase):
    """Mêmes restrictions de photos que pour les annonces de véhicules."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def payload(self, nb, **overrides):
        data = {
            'reference': 'DJP-200', 'name': 'Disque', 'category': self.category.pk, 'availability': 'a_confirmer',
            'compatibilities': '', 'is_active': 'on', 'photos': [png_upload(f'p{i}.png') for i in range(nb)],
        }
        data.update(overrides)
        return data

    def post(self, url, data):
        with override_settings(MEDIA_ROOT=self.media):
            return self.client.post(url, data)

    def test_creation_needs_at_least_three_photos(self):
        for nb in (0, 2):
            response = self.post(reverse('part_creer'), self.payload(nb))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Ajoutez au moins 3 photos')
        self.assertFalse(PartMirror.objects.using(DB).filter(reference='DJP-200').exists())
        response = self.post(reverse('part_creer'), self.payload(3))
        self.assertRedirects(response, reverse('part_liste'))

    def test_four_photos_maximum_in_total(self):
        response = self.post(reverse('part_creer'), self.payload(5))
        self.assertContains(response, 'plus de 4 photos')
        self.assertFalse(PartMirror.objects.using(DB).filter(reference='DJP-200').exists())
        part = self.make_part(reference='DJP-201')
        with override_settings(MEDIA_ROOT=self.media):
            for i in range(3):
                PartImageMirror(part=part, image=png_upload(f'k{i}.png'), order=i).save(using=DB)
        edit = self.payload(2, reference='DJP-201')
        response = self.post(reverse('part_modifier', args=[part.pk]), edit)
        self.assertContains(response, 'plus de 4 photos')  # 3 conservées + 2 nouvelles
        self.assertEqual(part.images.using(DB).count(), 3)

    def test_editing_an_existing_part_does_not_require_new_photos(self):
        part = self.make_part(reference='DJP-202')
        edit = self.payload(0, reference='DJP-202', name='Nouveau nom')
        response = self.post(reverse('part_modifier', args=[part.pk]), edit)
        self.assertRedirects(response, reverse('part_liste'))
        part.refresh_from_db(using=DB)
        self.assertEqual(part.name, 'Nouveau nom')

    def test_list_flags_parts_without_photo_and_filters_them(self):
        self.make_part(reference='NOPHOTO', name='Sans image')
        withp = self.make_part(reference='WITHPHOTO', name='Avec image')
        with override_settings(MEDIA_ROOT=self.media):
            PartImageMirror(part=withp, image=png_upload('x.png'), order=0).save(using=DB)
        html = self.client.get(reverse('part_liste')).content.decode()
        self.assertIn('Sans photo · non affichée', html)
        self.assertIn('1 photo', html)
        only = self.client.get(reverse('part_liste'), {'visibilite': 'sans_photo'}).content.decode()
        self.assertIn('Sans image', only)
        self.assertNotIn('Avec image', only)

    def test_form_and_import_pages_explain_the_rules(self):
        self.assertContains(self.client.get(reverse('part_creer')), '3 photos au minimum')
        self.assertContains(self.client.get(reverse('part_import')), "n'apparaît sur le site qu'une fois ses photos ajoutées")

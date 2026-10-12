import io
import shutil
import tempfile

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Part, PartCategory, PartCompatibility, PartRequest, normalize_reference


def make_part(category=None, **overrides):
    data = dict(
        reference='DJP-0001', name='Plaquettes de frein avant', manufacturer_reference='04465-33450',
        brand='Bosch', category=category or PartCategory.objects.get(name='Freinage'),
    )
    data.update(overrides)
    return Part.objects.create(**data)


class SeedAndHomeTests(TestCase):
    def test_spec_categories_are_seeded(self):
        names = set(PartCategory.objects.values_list('name', flat=True))
        for expected in ('Moteur', 'Freinage', 'Filtration', 'Carrosserie', 'Éclairage'):
            self.assertIn(expected, names)
        self.assertEqual(PartCategory.objects.count(), 10)

    def test_home_without_parts_does_not_pretend_to_have_a_catalog(self):
        response = self.client.get(reverse('parts:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trouvez les pièces')
        self.assertContains(response, 'en cours de constitution')
        self.assertNotContains(response, 'Pièces populaires')
        self.assertContains(response, 'Je ne trouve pas ma pièce')

    def test_home_lists_featured_parts_only_when_marked(self):
        make_part(is_featured=True)
        make_part(reference='DJP-0002', name='Filtre à huile', is_featured=False,
                  category=PartCategory.objects.get(name='Filtration'))
        response = self.client.get(reverse('parts:home'))
        self.assertContains(response, 'Pièces populaires')
        self.assertContains(response, 'Plaquettes de frein avant')
        self.assertNotContains(response, 'Filtre à huile')

    def test_old_pieces_url_is_served_by_the_new_module(self):
        self.assertEqual(reverse('parts:home'), '/pieces-detachees/')


class SearchTests(TestCase):
    def setUp(self):
        self.brake = make_part()
        PartCompatibility.objects.create(part=self.brake, make='Toyota', model='Corolla', year_from=2014, year_to=2019)
        self.filter = make_part(reference='DJP-0002', name='Filtre à huile', manufacturer_reference='90915-YZZE1',
                                brand='Toyota', category=PartCategory.objects.get(name='Filtration'),
                                price=4500, availability=Part.Availability.AVAILABLE)
        PartCompatibility.objects.create(part=self.filter, make='Toyota', model='', year_from=None, year_to=None)
        self.hidden = make_part(reference='DJP-0003', name='Disque caché', is_active=False)
        self.url = reverse('parts:search')

    def names(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return [p.name for p in response.context['page_obj']]

    def test_inactive_parts_are_hidden(self):
        self.assertNotIn('Disque caché', self.names())

    def test_search_by_name_is_accent_and_case_tolerant(self):
        self.assertEqual(self.names(q='FILTRE huile'), ['Filtre à huile'])
        self.assertEqual(self.names(q='filtre a huile'), ['Filtre à huile'])

    def test_search_by_reference_ignores_separators(self):
        self.assertEqual(self.names(q='0446533450'), ['Plaquettes de frein avant'])
        self.assertEqual(self.names(q='04465-33450'), ['Plaquettes de frein avant'])
        self.assertEqual(self.names(q='djp 0002'), ['Filtre à huile'])

    def test_filter_by_category_and_budget(self):
        self.assertEqual(self.names(categorie=PartCategory.objects.get(name='Filtration').pk), ['Filtre à huile'])
        self.assertEqual(self.names(budget='5000'), ['Filtre à huile'])  # sans prix = exclu

    def test_filter_by_vehicle_uses_declared_compatibilities_only(self):
        self.assertCountEqual(self.names(marque='toyota', modele='Corolla', annee='2016'),
                              ['Plaquettes de frein avant', 'Filtre à huile'])
        # Hors plage d'années : seule la pièce compatible « toute la marque » reste.
        self.assertEqual(self.names(marque='Toyota', modele='Corolla', annee='2010'), ['Filtre à huile'])
        self.assertEqual(self.names(marque='Peugeot'), [])

    def test_vehicle_search_without_result_proposes_the_request_form(self):
        response = self.client.get(self.url, {'q': 'courroie', 'marque': 'Kia', 'modele': 'Rio', 'annee': '2018'})
        self.assertContains(response, 'Aucune pièce ne correspond')
        self.assertContains(response, reverse('parts:request'))
        self.assertContains(response, 'piece_nom=courroie')

    def test_models_endpoint_lists_models_of_make(self):
        response = self.client.get(reverse('parts:models'), {'marque': 'Toyota'})
        self.assertContains(response, 'Corolla')
        self.assertNotContains(response, 'Peugeot')


class DetailTests(TestCase):
    def setUp(self):
        self.part = make_part()
        PartCompatibility.objects.create(part=self.part, make='Toyota', model='Corolla', year_from=2014, year_to=2019)

    def test_unknown_price_condition_and_availability_are_not_invented(self):
        response = self.client.get(self.part.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Prix sur demande')
        self.assertContains(response, 'Disponibilité à confirmer')
        self.assertContains(response, 'Non précisé')
        self.assertNotContains(response, 'immédiatement')
        self.assertNotContains(response, '"offers"')

    def test_available_part_with_price_exposes_offer(self):
        Part.objects.filter(pk=self.part.pk).update(price=12500, availability=Part.Availability.AVAILABLE,
                                                    condition=Part.Condition.NEW)
        response = self.client.get(self.part.get_absolute_url())
        self.assertRegex(response.content.decode(), r'12[\s  ]?500')
        self.assertContains(response, 'Disponible')
        self.assertContains(response, '"price": "12500"')

    def test_compatibility_messages_depend_on_declared_data(self):
        url = self.part.get_absolute_url()
        ok = self.client.get(url, {'marque': 'Toyota', 'modele': 'Corolla', 'annee': '2016'})
        self.assertContains(ok, 'Compatibilité renseignée')
        unknown = self.client.get(url, {'marque': 'Kia', 'modele': 'Rio', 'annee': '2016'})
        self.assertContains(unknown, 'non établie')
        self.assertNotContains(unknown, 'Compatibilité renseignée')
        none = self.client.get(url)
        self.assertNotContains(none, 'non établie')

    def test_wrong_slug_redirects_and_inactive_is_404(self):
        wrong = reverse('parts:detail', kwargs={'pk': self.part.pk, 'slug': 'mauvais'})
        self.assertRedirects(self.client.get(wrong), self.part.get_absolute_url(), status_code=301)
        Part.objects.filter(pk=self.part.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.part.get_absolute_url()).status_code, 404)


class PartRequestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('parts:request')
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def payload(self, **overrides):
        data = {
            'full_name': 'Jean Kouadio', 'phone': '07 00 00 00 00', 'make': 'Toyota', 'model': 'Corolla',
            'year': '2015', 'engine': '', 'part_name': 'Amortisseur arrière', 'part_reference': '',
            'description': 'Bruit sur le côté gauche, deux pièces.',
        }
        data.update(overrides)
        return data

    def test_form_is_prefilled_from_search(self):
        response = self.client.get(self.url, {'piece_nom': 'courroie', 'marque': 'Kia', 'modele': 'Rio', 'annee': '2018'})
        self.assertContains(response, 'value="courroie"')
        self.assertContains(response, 'value="Kia"')

    @override_settings(PARTS_NOTIFY_EMAILS=['pieces@example.com'])
    def test_valid_request_is_saved_notified_and_confirmed(self):
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, reverse('parts:request_success'), fetch_redirect_response=False)
        request = PartRequest.objects.get()
        self.assertEqual(request.reference, f'DJ-PC-{timezone.localdate().year}-0001')
        self.assertEqual(request.phone, '+225 0700000000')
        self.assertEqual(request.status, PartRequest.Status.NEW)
        self.assertIsNone(request.part)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(request.reference, mail.outbox[0].subject)
        success = self.client.get(reverse('parts:request_success'))
        self.assertContains(success, request.reference)
        # La référence n'est montrée qu'une fois.
        self.assertRedirects(self.client.get(reverse('parts:request_success')), self.url)

    def test_request_from_catalog_part_is_linked_to_it(self):
        part = make_part()
        response = self.client.post(self.url, self.payload(piece=part.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PartRequest.objects.get().part, part)

    def test_required_fields_and_validation(self):
        for field in ('full_name', 'phone', 'make', 'model', 'year', 'part_name', 'description'):
            response = self.client.post(self.url, self.payload(**{field: ''}))
            self.assertEqual(response.status_code, 200, field)
            self.assertIn(field, response.context['form'].errors)
        self.assertEqual(PartRequest.objects.count(), 0)
        self.assertIn('phone', self.client.post(self.url, self.payload(phone='123')).context['form'].errors)
        self.assertIn('year', self.client.post(self.url, self.payload(year='1800')).context['form'].errors)

    def test_optional_fields_and_photo(self):
        with override_settings(MEDIA_ROOT=self.media):
            buffer = io.BytesIO()
            Image.new('RGB', (4, 4), 'white').save(buffer, 'PNG')
            png = buffer.getvalue()
            photo = SimpleUploadedFile('piece.png', png, content_type='image/png')
            response = self.client.post(self.url, self.payload(photo=photo, engine='1.6 essence', part_reference='48157'))
        self.assertEqual(response.status_code, 302)
        request = PartRequest.objects.get()
        self.assertTrue(request.photo.name.startswith('part_requests/'))
        self.assertEqual(request.engine, '1.6 essence')

    def test_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trop de demandes')
        self.assertEqual(PartRequest.objects.count(), 5)


class HelperTests(TestCase):
    def test_normalize_reference(self):
        self.assertEqual(normalize_reference('04465-33450'), '0446533450')
        self.assertEqual(normalize_reference('djp 0002'), 'DJP0002')
        self.assertEqual(normalize_reference(None), '')

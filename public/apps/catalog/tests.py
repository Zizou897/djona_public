from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Seller, Vehicle, VehicleImage


class SellerProfileTests(TestCase):
    def make_seller(self, **overrides):
        data = dict(
            source_vendeur_id=9001, first_name='Awa', last_name='Traoré', phone='0700000000',
            type_compte=Seller.TypeCompte.PROFESSIONNEL, company_name='Auto Prestige',
            city=Seller.Ville.ABIDJAN_COCODY, member_since=timezone.now(),
        )
        data.update(overrides)
        return Seller.objects.create(**data)

    def test_verified_company_badge_only_when_verified(self):
        seller = self.make_seller(showroom_address='Riviera 2, Abidjan')
        response = self.client.get(seller.get_absolute_url())
        self.assertContains(response, 'Auto Prestige')
        self.assertNotContains(response, 'Entreprise vérifiée')
        self.assertContains(response, 'Showroom : Riviera 2, Abidjan')

        Seller.objects.filter(pk=seller.pk).update(is_verified_company=True)
        response = self.client.get(seller.get_absolute_url())
        self.assertContains(response, 'Entreprise vérifiée')
        self.assertContains(response, "justificatif d'entreprise (RCCM) a été contrôlé")

    def test_no_unverified_claims(self):
        seller = self.make_seller()
        content = self.client.get(seller.get_absolute_url()).content.decode()
        self.assertNotIn('Certifié', content)
        self.assertNotIn('concessionnaire', content)
        self.assertNotIn("processus d'inspection", content)
        self.assertNotIn('immatriculation', content)

    def test_individual_seller_has_no_company_line(self):
        seller = self.make_seller(source_vendeur_id=9002, type_compte=Seller.TypeCompte.PARTICULIER, company_name='')
        response = self.client.get(seller.get_absolute_url())
        self.assertContains(response, 'Awa Traoré')
        self.assertNotContains(response, 'À propos du vendeur')


    def test_synced_vehicle_condition_not_shown(self):
        seller = self.make_seller(source_vendeur_id=9003)
        vehicle = Vehicle.objects.create(
            brand='Toyota', model_name='Corolla', year=2022, price=8_500_000, mileage=15_000,
            fuel_type='essence', transmission='automatique', city='Abidjan', seller=seller,
            source_annonce_id=4242,
        )
        VehicleImage.objects.create(vehicle=vehicle, image='vehicles/annonce-4242/a.webp', order=0)
        content = self.client.get(seller.get_absolute_url()).content.decode()
        self.assertIn('Toyota Corolla', content)
        self.assertNotIn('>Occasion<', content)


class VehicleCityConditionTests(TestCase):
    def make_vehicle(self, **overrides):
        seller = Seller.objects.create(source_vendeur_id=9100, first_name='Jean', last_name='Kouadio', member_since=timezone.now())
        data = dict(brand='Toyota', model_name='Yaris', year=2021, price=6_500_000, mileage=30_000,
                    fuel_type='essence', transmission='manuelle', seller=seller, source_annonce_id=5151)
        data.update(overrides)
        vehicle = Vehicle.objects.create(**data)
        VehicleImage.objects.create(vehicle=vehicle, image='vehicles/annonce-5151/a.webp', order=0)
        return vehicle

    def test_unknown_city_and_condition_are_not_invented(self):
        vehicle = self.make_vehicle()
        content = self.client.get(vehicle.get_absolute_url()).content.decode()
        self.assertIn('Non précisé', content)
        self.assertNotIn('Occasion', content)
        self.assertNotIn('"itemCondition"', content)
        self.assertNotIn('"@type": "City"', content)

    def test_known_city_and_condition_are_shown(self):
        vehicle = self.make_vehicle(city='Abidjan, Cocody', condition='neuf')
        content = self.client.get(vehicle.get_absolute_url()).content.decode()
        self.assertIn('Abidjan, Cocody', content)
        self.assertIn('Neuf', content)
        self.assertIn('https://schema.org/NewCondition', content)


class MarketplaceOnlyWithPhotosTests(TestCase):
    """La marketplace n'affiche que les véhicules publiés qui ont au moins une photo."""

    def setUp(self):
        self.seller = Seller.objects.create(source_vendeur_id=9200, first_name='Awa', last_name='Traoré', member_since=timezone.now())
        self.with_photo = self.make('Kia', 'Rio', photo=True)
        self.without_photo = self.make('Peugeot', '208', photo=False)
        self.unpublished = self.make('Audi', 'A3', photo=True, publish=False)

    def make(self, brand, model, photo, **extra):
        vehicle = Vehicle.objects.create(
            brand=brand, model_name=model, year=2020, price=5_000_000, mileage=40_000, fuel_type='essence',
            transmission='manuelle', seller=self.seller, publish=extra.get('publish', True),
        )
        if photo:
            VehicleImage.objects.create(vehicle=vehicle, image=f'vehicles/{model}.webp', order=0)
        return vehicle

    def test_queryset_only_returns_published_vehicles_with_photo(self):
        self.assertEqual(list(Vehicle.objects.marketplace()), [self.with_photo])

    def test_vehicle_with_several_photos_is_listed_once(self):
        VehicleImage.objects.create(vehicle=self.with_photo, image='vehicles/Rio-2.webp', order=1)
        self.assertEqual(Vehicle.objects.marketplace().count(), 1)

    def test_catalog_hides_vehicle_without_photo(self):
        content = self.client.get(reverse('catalog:list')).content.decode()
        self.assertIn('Kia', content)
        self.assertNotIn('Peugeot', content)
        self.assertNotIn('Audi', content)

    def test_detail_of_vehicle_without_photo_is_not_found(self):
        self.assertEqual(self.client.get(self.with_photo.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.without_photo.get_absolute_url()).status_code, 404)

    def test_seller_page_home_and_sitemap_ignore_vehicle_without_photo(self):
        seller_page = self.client.get(self.seller.get_absolute_url()).content.decode()
        self.assertIn('Kia Rio', seller_page)
        self.assertNotIn('Peugeot 208', seller_page)
        home = self.client.get(reverse('core:home')).content.decode()
        self.assertNotIn('Peugeot', home)
        sitemap = self.client.get('/sitemap.xml').content.decode()
        self.assertIn(self.with_photo.slug, sitemap)
        self.assertNotIn(self.without_photo.slug, sitemap)


class ListingCardClickableTests(TestCase):
    def test_whole_card_including_image_is_one_link(self):
        import re
        seller = Seller.objects.create(source_vendeur_id=9300, first_name='Awa', last_name='Traoré', member_since=timezone.now())
        vehicle = Vehicle.objects.create(brand='Kia', model_name='Rio', year=2020, price=5_000_000, mileage=40_000,
                                         fuel_type='essence', transmission='manuelle', seller=seller)
        VehicleImage.objects.create(vehicle=vehicle, image='vehicles/rio.webp', order=0)
        html = self.client.get(reverse('catalog:list')).content.decode()
        card = re.search(r'<a href="%s"[^>]*>(.*?)</a>' % re.escape(vehicle.get_absolute_url()), html, re.S)
        self.assertIsNotNone(card)
        self.assertIn('<img', card.group(1))            # l'image est dans le lien
        self.assertIn('Kia Rio 2020', card.group(1))    # le titre aussi
        self.assertIn('FCFA', card.group(1))            # et le prix
        self.assertNotIn('<a ', card.group(1))          # pas de lien imbriqué

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Seller, Vehicle


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
        Vehicle.objects.create(
            brand='Toyota', model_name='Corolla', year=2022, price=8_500_000, mileage=15_000,
            fuel_type='essence', transmission='automatique', city='Abidjan', seller=seller,
            source_annonce_id=4242,
        )
        content = self.client.get(seller.get_absolute_url()).content.decode()
        self.assertIn('Toyota Corolla', content)
        self.assertNotIn('>Occasion<', content)


class VehicleCityConditionTests(TestCase):
    def make_vehicle(self, **overrides):
        seller = Seller.objects.create(source_vendeur_id=9100, first_name='Jean', last_name='Kouadio', member_since=timezone.now())
        data = dict(brand='Toyota', model_name='Yaris', year=2021, price=6_500_000, mileage=30_000,
                    fuel_type='essence', transmission='manuelle', seller=seller, source_annonce_id=5151)
        data.update(overrides)
        return Vehicle.objects.create(**data)

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

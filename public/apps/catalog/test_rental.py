from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Seller, Vehicle, VehicleImage


class RentalBase(TestCase):
    def setUp(self):
        self.seller = Seller.objects.create(source_vendeur_id=9400, first_name='Awa', last_name='Traoré', member_since=timezone.now())
        self.sale = self.make('Kia', 'Rio', price=5_000_000)
        self.sale_cheap = self.make('Peugeot', '208', price=3_000_000)
        self.rent_day = self.make('Toyota', 'Prado', listing_type='location', rent_price_day=60_000, deposit=500_000)
        self.rent_all = self.make('Hyundai', 'Tucson', listing_type='location', rent_price_day=40_000,
                                  rent_price_week=240_000, rent_price_month=800_000)
        self.rent_month = self.make('Nissan', 'Qashqai', listing_type='location', rent_price_month=600_000)

    def make(self, brand, model, price=0, **extra):
        vehicle = Vehicle.objects.create(
            brand=brand, model_name=model, year=2021, price=price, mileage=30_000, fuel_type='essence',
            transmission='automatique', seller=self.seller, **extra,
        )
        VehicleImage.objects.create(vehicle=vehicle, image=f'vehicles/{model}.webp', order=0)
        return vehicle

    def names(self, **params):
        response = self.client.get(reverse('catalog:list'), params)
        self.assertEqual(response.status_code, 200)
        return [v.model_name for v in response.context['page_obj']]


class VehicleModelTests(RentalBase):
    def test_price_label_and_rates(self):
        self.assertTrue(self.sale.price_label.endswith('FCFA'))
        self.assertFalse(self.sale.is_rental)
        self.assertEqual(self.rent_day.price_label.split(' FCFA')[1], ' / jour')
        self.assertEqual([r['period'] for r in self.rent_all.rental_rates], ['jour', 'semaine', 'mois'])
        self.assertEqual(self.rent_month.price_label.split('FCFA')[1], ' / mois')
        self.assertEqual(self.make('Kia', 'Picanto', listing_type='location').price_label, 'Tarif non renseigné')

    def test_querysets(self):
        self.assertEqual(Vehicle.objects.for_sale().count(), 2)
        self.assertEqual(Vehicle.objects.for_rent().count(), 3)


class CatalogFilterTests(RentalBase):
    def test_default_lists_everything_sales_first_when_sorted_by_price(self):
        self.assertEqual(len(self.names()), 5)
        self.assertEqual(self.names(sort='price_asc')[:2], ['208', 'Rio'])
        self.assertEqual(self.names(sort='price_desc')[:2], ['Rio', '208'])

    def test_buy_and_rent_filters(self):
        self.assertCountEqual(self.names(type='achat'), ['Rio', '208'])
        self.assertCountEqual(self.names(type='location'), ['Prado', 'Tucson', 'Qashqai'])

    def test_rent_period_filter(self):
        self.assertCountEqual(self.names(type='location', period='jour'), ['Prado', 'Tucson'])
        self.assertCountEqual(self.names(type='location', period='semaine'), ['Tucson'])
        self.assertCountEqual(self.names(type='location', period='mois'), ['Tucson', 'Qashqai'])

    def test_budget_only_applies_to_purchases(self):
        self.assertEqual(self.names(price_max='4000000'), ['208'])
        self.assertCountEqual(self.names(price_min='1', type='achat'), ['Rio', '208'])
        # Le budget d'achat ne masque pas les locations quand on ne regarde que les locations.
        self.assertEqual(len(self.names(type='location', price_max='1000')), 3)

    def test_rent_sorted_by_price_per_day_equivalent(self):
        # Tucson 40 000/j  <  Qashqai 600 000/mois (=20 000/j) ? non : 20 000 < 40 000 < 60 000
        self.assertEqual(self.names(type='location', sort='price_asc'), ['Qashqai', 'Tucson', 'Prado'])
        self.assertEqual(self.names(type='location', sort='price_desc'), ['Prado', 'Tucson', 'Qashqai'])

    def test_filter_ui_and_card_badges(self):
        html = self.client.get(reverse('catalog:list')).content.decode()
        for label in ('Je veux', 'Acheter', 'Louer', 'Période de location', 'Budget d&#x27;achat'):
            self.assertTrue(label in html or label.replace('&#x27;', "'") in html, label)
        self.assertIn('À louer', html)
        self.assertIn('FCFA / jour', html)
        self.assertIn('FCFA / mois', html)

    def test_home_stats_count_sales_and_rentals_separately(self):
        html = self.client.get(reverse('core:home')).content.decode()
        self.assertIn('Véhicules en vente', html)
        self.assertIn('Véhicules à louer', html)


class DetailAndCompareTests(RentalBase):
    def test_rental_detail_shows_rates_and_deposit(self):
        html = self.client.get(self.rent_all.get_absolute_url()).content.decode()
        self.assertIn('À louer', html)
        self.assertIn('Par jour', html)
        self.assertIn('Par semaine', html)
        self.assertIn('Par mois', html)
        self.assertIn('LeaseOut', html)
        self.assertNotIn('Caution', html)  # pas de caution renseignée sur ce véhicule
        html = self.client.get(self.rent_day.get_absolute_url()).content.decode()
        self.assertIn('Caution', html)
        self.assertIn('/ jour', html)
        self.assertNotIn('Par semaine', html)  # période non proposée = non affichée

    def test_sale_detail_is_unchanged(self):
        html = self.client.get(self.sale.get_absolute_url()).content.decode()
        self.assertNotIn('LeaseOut', html)
        self.assertNotIn('Caution', html)
        self.assertIn('"price": 5000000', html)

    def test_compare_shows_labels_and_does_not_favour_rentals(self):
        session = self.client.session
        session['compare_ids'] = [self.sale.id, self.rent_day.id]
        session.save()
        response = self.client.get(reverse('catalog:compare'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('/ jour', html)
        self.assertEqual(response.context['expert_pick_id'], self.sale.id)


class _FakeAnnonces(list):
    def values_list(self, *fields, flat=False):
        return [getattr(a, fields[0]) for a in self]


class SyncRentalTests(TestCase):
    """La commande de synchro copie type, tarifs et caution de l'annonce vendeur."""

    def annonce(self, **extra):
        data = dict(
            id=77, marque='Toyota', modele='Prado', annee=2020, prix=0, kilometrage=40000, carburant='diesel',
            boite_vitesses='automatique', couleur='Blanc', etat='occasion', ville='abidjan_cocody',
            description='Test', type_annonce='location', prix_jour=60000, prix_semaine=None, prix_mois=900000,
            caution=500000, vendeur=SimpleNamespace(id=1),
        )
        data.update(extra)
        return SimpleNamespace(**data)

    def run_sync(self, *annonces):
        from apps.vendor_sync.management.commands import sync_validated_annonces as module

        seller, _ = Seller.objects.get_or_create(source_vendeur_id=9500, defaults={'first_name': 'Awa', 'last_name': 'Traoré', 'member_since': timezone.now()})
        fake = mock.MagicMock()
        fake.objects.using.return_value.filter.return_value.select_related.return_value = _FakeAnnonces(annonces)
        with mock.patch.object(module, 'AnnonceMirror', fake),                 mock.patch.object(module.Command, '_sync_seller', return_value=seller),                 mock.patch.object(module.Command, '_sync_photos', return_value=0):
            module.Command().handle()

    def test_rental_annonce_becomes_a_rental_vehicle(self):
        self.run_sync(self.annonce())
        vehicle = Vehicle.objects.get(source_annonce_id=77)
        self.assertTrue(vehicle.is_rental)
        self.assertEqual((vehicle.price, vehicle.rent_price_day, vehicle.rent_price_week, vehicle.rent_price_month, vehicle.deposit),
                         (0, 60000, None, 900000, 500000))
        self.assertEqual([r['period'] for r in vehicle.rental_rates], ['jour', 'mois'])

    def test_sale_annonce_and_unknown_type_stay_sales(self):
        self.run_sync(self.annonce(id=78, type_annonce='vente', prix=8_500_000, prix_jour=None, prix_mois=None, caution=None),
                      self.annonce(id=79, type_annonce='inconnu', prix=1_000_000, prix_jour=None, prix_mois=None, caution=None))
        for annonce_id in (78, 79):
            vehicle = Vehicle.objects.get(source_annonce_id=annonce_id)
            self.assertFalse(vehicle.is_rental)
            self.assertIsNone(vehicle.deposit)

    def test_resync_updates_tariffs(self):
        self.run_sync(self.annonce())
        self.run_sync(self.annonce(prix_jour=45000, prix_mois=None, caution=None))
        vehicle = Vehicle.objects.get(source_annonce_id=77)
        self.assertEqual((vehicle.rent_price_day, vehicle.rent_price_month, vehicle.deposit), (45000, None, None))


class RentalDurationTests(TestCase):
    """Courte / moyenne / longue durée : seuils uniques (apps/catalog/rental.py)."""

    def test_category_boundaries(self):
        from .rental import duration_category

        cases = {1: 'courte', 7: 'courte', 8: 'moyenne', 29: 'moyenne', 30: 'longue', 400: 'longue'}
        for days, key in cases.items():
            self.assertEqual(duration_category(days)['key'], key, days)
        self.assertIsNone(duration_category(0))
        self.assertIsNone(duration_category(-3))

    def test_days_exclude_the_return_day(self):
        from datetime import date

        from .rental import rental_days

        self.assertEqual(rental_days(date(2026, 12, 1), date(2026, 12, 4)), 3)
        self.assertEqual(rental_days(date(2026, 12, 1), date(2026, 12, 1)), 0)

    def test_categories_are_contiguous(self):
        from .rental import RENTAL_CATEGORIES

        for previous, current in zip(RENTAL_CATEGORIES, RENTAL_CATEGORIES[1:]):
            self.assertEqual(previous['max_days'] + 1, current['min_days'])
        self.assertIsNone(RENTAL_CATEGORIES[-1]['max_days'])


class RentalRequestTests(RentalBase):
    def setUp(self):
        super().setUp()
        from django.core.cache import cache

        cache.clear()  # la demande d'intérêt est limitée par IP
        self.today = timezone.localdate()

    def post(self, vehicle, **data):
        payload = {'name': 'Kouadio', 'phone': '0700000000'}
        payload.update(data)
        response = self.client.post(reverse('catalog:express_interest', args=[vehicle.slug]), payload,
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        return response.json()

    def day(self, offset):
        return (self.today + timezone.timedelta(days=offset)).isoformat()

    def test_rental_request_stores_dates_and_duration(self):
        from .models import Interest

        result = self.post(self.rent_day, rental_start=self.day(2), rental_end=self.day(5))
        self.assertEqual(result['status'], 'success')
        self.assertIn('location', result['message'])
        interest = Interest.objects.get()
        self.assertEqual(interest.rental_days, 3)
        self.assertEqual(interest.rental_duration_label, 'Courte durée — 3 jours')

    def test_duration_label_for_each_category(self):
        from .models import Interest

        for end, expected in ((8, 'Courte durée — 7 jours'), (10, 'Moyenne durée — 9 jours'), (32, 'Longue durée — 31 jours')):
            Interest.objects.all().delete()
            self.post(self.rent_all, rental_start=self.day(1), rental_end=self.day(end))
            self.assertEqual(Interest.objects.get().rental_duration_label, expected)

    def test_rental_requires_valid_dates(self):
        from .models import Interest

        bad = [
            {},                                                                       # aucune date
            {'rental_start': self.day(2)},                                            # retour manquant
            {'rental_start': self.day(-1), 'rental_end': self.day(3)},                # début dans le passé
            {'rental_start': self.day(3), 'rental_end': self.day(3)},                 # retour le jour du début
            {'rental_start': self.day(5), 'rental_end': self.day(2)},                 # retour avant le début
            {'rental_start': 'pas-une-date', 'rental_end': self.day(3)},              # format invalide
        ]
        for data in bad:
            result = self.post(self.rent_day, **data)
            self.assertEqual(result['status'], 'error', data)
        self.assertEqual(Interest.objects.count(), 0)

    def test_error_message_names_the_date_problem(self):
        result = self.post(self.rent_day, rental_start=self.day(5), rental_end=self.day(2))
        self.assertIn('postérieure', result['message'])
        result = self.post(self.rent_day, rental_start=self.day(-1), rental_end=self.day(2))
        self.assertIn('passé', result['message'])

    def test_sale_ignores_any_dates(self):
        from .models import Interest

        result = self.post(self.sale, rental_start=self.day(2), rental_end=self.day(5))
        self.assertEqual(result['status'], 'success')
        interest = Interest.objects.get()
        self.assertIsNone(interest.rental_start)
        self.assertEqual(interest.rental_duration_label, '')

    def test_missing_contact_still_reports_contact_error(self):
        result = self.post(self.rent_day, name='', rental_start=self.day(2), rental_end=self.day(5))
        self.assertEqual(result['status'], 'error')
        self.assertIn('nom', result['message'])


class RentalDetailPageTests(RentalBase):
    def test_rental_page_offers_dates_and_the_three_categories(self):
        html = self.client.get(self.rent_all.get_absolute_url()).content.decode()
        for expected in ('Louer avec Djona', 'id="rental-start"', 'id="rental-end"', 'Courte durée', 'Moyenne durée',
                         'Longue durée', '1 à 7 jours', '30 jours et plus', 'rental-dates.js', 'id="interest-rental-start"'):
            self.assertIn(expected, html)
        self.assertNotIn('Acheter avec Djona', html)
        self.assertNotIn('Je suis intéressé', html)  # la demande passe par « Louer avec Djona » (dates requises)

    def test_sale_page_has_no_rental_widgets(self):
        html = self.client.get(self.sale.get_absolute_url()).content.decode()
        for absent in ('rental-card', 'rental-start', 'rental-dates.js', 'Louer avec Djona', 'interest-rental-start'):
            self.assertNotIn(absent, html)
        self.assertIn('Acheter avec Djona', html)
        self.assertIn('Je suis intéressé', html)

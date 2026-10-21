from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from parts.models import (DeliveryZoneMirror, PartOrderEventMirror, PartOrderLineMirror, PartOrderMirror,
                          PartsSettingsMirror)

User = get_user_model()
DB = 'public_db'


class OrdersBase(TestCase):
    databases = {'default', DB}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-orders', password='motdepasse', is_staff=True)
        self.client.force_login(self.admin)
        self.order = self.make_order()

    def tearDown(self):
        PartOrderEventMirror.objects.using(DB).all().delete()
        PartOrderLineMirror.objects.using(DB).all().delete()
        PartOrderMirror.objects.using(DB).all().delete()
        DeliveryZoneMirror.objects.using(DB).all().delete()
        PartsSettingsMirror.objects.using(DB).all().delete()

    def make_order(self, reference='DJP-CMD-2026-9001', **overrides):
        data = dict(reference=reference, customer_type='particulier', full_name='Jean Kouadio', phone='+225 0700000000',
                    reception='retrait', subtotal=80000, delivery_fee=0, created_at=timezone.now())
        data.update(overrides)
        order = PartOrderMirror.objects.using(DB).create(**data)
        PartOrderLineMirror.objects.using(DB).create(order=order, name='Disque de frein', reference='OEM-D1', unit_price=40000, quantity=2)
        PartOrderEventMirror.objects.using(DB).create(order=order, status='en_attente', note='Commande reçue')
        return order

    def detail_url(self, order=None):
        return reverse('part_commande_detail', args=[(order or self.order).pk])

    def change_status(self, new, note='', order=None):
        return self.client.post(self.detail_url(order), {'action': 'statut', 'statut': new, 'note': note})


class AccessTests(OrdersBase):
    def test_pages_require_staff(self):
        self.client.logout()
        for name in ('part_commande_liste', 'part_zone_liste', 'part_reglages'):
            url = reverse(name)
            self.assertRedirects(self.client.get(url), f"{reverse('connexion_admin')}?next={url}", msg_prefix=name)


class OrderListTests(OrdersBase):
    def test_list_search_and_filters(self):
        other = self.make_order('DJP-CMD-2026-9002', full_name='Awa Traoré', reception='livraison', zone_name='Abidjan',
                                company_name='Garage Auto', status='confirmee', payment_status='paye')
        html = self.client.get(reverse('part_commande_liste')).content.decode()
        self.assertIn('DJP-CMD-2026-9001', html)
        self.assertIn('Awa Traoré (Garage Auto)', html)
        only = lambda **p: self.client.get(reverse('part_commande_liste'), p).content.decode()
        self.assertNotIn('9001', only(statut='confirmee'))
        self.assertIn('9002', only(reception='livraison'))
        self.assertNotIn('9002', only(reception='retrait'))
        self.assertIn('9002', only(paiement='paye'))
        self.assertIn('9001', only(q='OEM-D1'))      # recherche par référence de pièce
        self.assertNotIn('9002', only(q='Kouadio'))
        self.assertIn('9002', only(q='Garage'))

    def test_counter_exposes_pending_orders(self):
        self.make_order('DJP-CMD-2026-9003', status='confirmee')
        counters = self.client.get(reverse('compteurs_admin')).json()
        self.assertEqual(counters.get('commandes_pieces'), 1)


class OrderDetailTests(OrdersBase):
    def test_detail_shows_lines_totals_and_journal(self):
        html = self.client.get(self.detail_url()).content.decode()
        for expected in ('Disque de frein', 'OEM-D1', '80', 'Retrait', 'Commande reçue', 'En attente de confirmation'):
            self.assertIn(expected, html)

    def test_only_allowed_transitions_are_offered_and_applied(self):
        html = self.client.get(self.detail_url()).content.decode()
        self.assertIn('value="confirmee"', html)
        self.assertNotIn('value="livree_retiree"', html)
        self.change_status('confirmee', 'Client rappelé')
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.status, 'confirmee')
        event = self.order.events.using(DB).last()
        self.assertEqual((event.status, event.note), ('confirmee', 'Client rappelé'))

    def test_forbidden_transition_is_rejected_and_logged_nowhere(self):
        self.change_status('livree_retiree')  # impossible depuis « en attente »
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.status, 'en_attente')
        self.assertEqual(self.order.events.using(DB).count(), 1)

    def test_pickup_and_delivery_follow_different_paths(self):
        self.change_status('confirmee')
        self.change_status('en_preparation')
        self.change_status('en_livraison')        # refusé pour un retrait
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.status, 'en_preparation')
        self.change_status('prete_retrait')
        self.change_status('livree_retiree')
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.status, 'livree_retiree')
        self.change_status('annulee')              # une commande livrée ne peut plus être annulée
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.status, 'livree_retiree')

        delivery = self.make_order('DJP-CMD-2026-9005', reception='livraison', status='en_preparation', delivery_fee=None)
        self.change_status('prete_retrait', order=delivery)
        delivery.refresh_from_db(using=DB)
        self.assertEqual(delivery.status, 'en_preparation')
        self.change_status('en_livraison', order=delivery)
        delivery.refresh_from_db(using=DB)
        self.assertEqual(delivery.status, 'en_livraison')

    def test_cancelled_order_can_never_become_delivered(self):
        self.change_status('annulee')
        for target in ('livree_retiree', 'confirmee', 'en_preparation'):
            self.change_status(target)
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.status, 'annulee')

    def test_payment_fees_commission_and_note_are_saved_and_logged(self):
        response = self.client.post(self.detail_url(), {
            'action': 'suivi', 'delivery_fee': '0', 'commission_amount': '4000', 'payment_status': 'partiel',
            'payment_method': 'Mobile Money', 'payment_reference': 'MM-123', 'amount_paid': '30000',
            'internal_note': 'Acompte reçu.',
        })
        self.assertRedirects(response, self.detail_url())
        self.order.refresh_from_db(using=DB)
        self.assertEqual((self.order.payment_status, self.order.payment_method, self.order.amount_paid, self.order.commission_amount),
                         ('partiel', 'Mobile Money', 30000, 4000))
        self.assertEqual(self.order.balance, 50000)
        self.assertIn('Mise à jour', self.order.events.using(DB).last().note)

    def test_overpayment_is_refused_when_the_total_is_final(self):
        response = self.client.post(self.detail_url(), {
            'action': 'suivi', 'delivery_fee': '0', 'payment_status': 'paye', 'amount_paid': '999999',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('amount_paid', response.context['form'].errors)
        self.order.refresh_from_db(using=DB)
        self.assertEqual(self.order.amount_paid, 0)


class ZonesAndSettingsTests(OrdersBase):
    def test_zone_crud_and_duplicates(self):
        self.client.post(reverse('part_zone_liste'), {'name': 'Abidjan', 'fee': '3000', 'lead_time': '24 h', 'order': 1})
        zone = DeliveryZoneMirror.objects.using(DB).get(name='Abidjan')
        self.assertEqual((zone.fee, zone.lead_time), (3000, '24 h'))
        response = self.client.post(reverse('part_zone_liste'), {'name': 'abidjan', 'order': 2})
        self.assertIn('name', response.context['form'].errors)
        self.client.post(reverse('part_zone_modifier', args=[zone.pk]), {'name': 'Grand Abidjan', 'fee': '', 'lead_time': '48 h', 'order': 1})
        zone.refresh_from_db(using=DB)
        self.assertEqual((zone.name, zone.fee), ('Grand Abidjan', None))   # frais vides = à confirmer
        self.client.post(reverse('part_zone_basculer', args=[zone.pk]))
        zone.refresh_from_db(using=DB)
        self.assertFalse(zone.is_active)

    def test_settings_commission_rule_is_validated(self):
        url = reverse('part_reglages')
        self.assertContains(self.client.get(url), 'Aucune (non définie)')
        bad = self.client.post(url, {'commission_type': 'pourcentage', 'commission_value': '', 'payment_terms': '', 'pickup_instructions': ''})
        self.assertIn('commission_value', bad.context['form'].errors)
        bad = self.client.post(url, {'commission_type': 'pourcentage', 'commission_value': '150', 'payment_terms': '', 'pickup_instructions': ''})
        self.assertIn('commission_value', bad.context['form'].errors)
        ok = self.client.post(url, {'commission_type': 'pourcentage', 'commission_value': '8', 'payment_terms': 'Paiement au retrait.',
                                    'pickup_instructions': 'Angré 9e tranche.'})
        self.assertRedirects(ok, url)
        settings_ = PartsSettingsMirror.objects.using(DB).get(pk=1)
        self.assertEqual((settings_.commission_type, float(settings_.commission_value), settings_.payment_terms), ('pourcentage', 8.0, 'Paiement au retrait.'))
        self.client.post(url, {'commission_type': 'aucune', 'commission_value': '8', 'payment_terms': '', 'pickup_instructions': ''})
        settings_.refresh_from_db(using=DB)
        self.assertIsNone(settings_.commission_value)  # sans règle, aucune valeur conservée

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import cart as cart_service
from .models import DeliveryZone, Part, PartImage, PartOrder, PartOrderEvent, PartsSettings

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def make_part(reference, name, category=None, photo=True, **extra):
    from .models import PartCategory
    part = Part.objects.create(reference=reference, name=name, manufacturer_reference=f'OEM-{reference}',
                               category=category or PartCategory.objects.get(name='Freinage'), **extra)
    if photo:
        PartImage.objects.create(part=part, image=f'parts/{reference}.webp', order=0)
    return part


class CartTests(TestCase):
    def setUp(self):
        cache.clear()
        self.disc = make_part('D-1', 'Disque de frein', price=40000, availability=Part.Availability.AVAILABLE)
        self.pad = make_part('P-1', 'Plaquettes', price=25000)
        self.quote = make_part('Q-1', 'Étrier sur devis')  # prix non renseigné
        self.gone = make_part('G-1', 'Pièce indisponible', price=10000, availability=Part.Availability.UNAVAILABLE)

    def add(self, part, quantity=1, ajax=True):
        return self.client.post(reverse('parts:cart_add', args=[part.pk]), {'quantity': quantity}, **(AJAX if ajax else {}))

    def test_add_returns_count_and_accumulates(self):
        data = self.add(self.disc, 2).json()
        self.assertEqual((data['status'], data['count']), ('success', 2))
        self.assertEqual(self.add(self.disc).json()['count'], 3)
        self.assertEqual(self.add(self.pad).json()['count'], 4)

    def test_add_without_javascript_redirects_to_the_cart(self):
        self.assertRedirects(self.add(self.disc, ajax=False), reverse('parts:cart'), fetch_redirect_response=False)

    def test_bad_quantity_defaults_to_one_and_is_capped(self):
        self.assertEqual(self.add(self.disc, 'abc').json()['count'], 1)
        self.assertEqual(self.add(self.disc, 500).json()['count'], cart_service.MAX_QUANTITY)

    def test_unavailable_hidden_and_photoless_parts_cannot_be_added(self):
        self.assertEqual(self.add(self.gone).status_code, 409)
        hidden = make_part('H-1', 'Masquée', price=1000, is_active=False)
        photoless = make_part('N-1', 'Sans photo', price=1000, photo=False)
        self.assertEqual(self.add(hidden).status_code, 404)
        self.assertEqual(self.add(photoless).status_code, 404)
        self.assertEqual(self.client.get(reverse('parts:cart')).context['cart'].count, 0)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse('parts:cart_add', args=[self.disc.pk])).status_code, 405)

    def test_cart_page_totals_and_unpriced_parts(self):
        self.add(self.disc, 2)
        self.add(self.pad)
        self.add(self.quote)
        response = self.client.get(reverse('parts:cart'))
        cart = response.context['cart']
        self.assertEqual((cart.count, cart.subtotal, cart.unpriced_count), (4, 2 * 40000 + 25000, 1))
        html = response.content.decode()
        self.assertIn('Prix sur demande', html)
        self.assertIn('Pièces sur devis', html)
        self.assertIn('Aucun paiement à cette étape', html)

    def test_update_and_remove_with_htmx_and_without(self):
        self.add(self.disc, 2)
        url = reverse('parts:cart_update', args=[self.disc.pk])
        fragment = self.client.post(url, {'quantity': 5}, HTTP_HX_REQUEST='true')
        self.assertNotIn('<html', fragment.content.decode())
        self.assertEqual(fragment.context['cart'].count, 5)
        self.assertRedirects(self.client.post(url, {'quantity': 1}), reverse('parts:cart'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('parts:cart')).context['cart'].count, 1)
        self.client.post(url, {'quantity': 0})
        self.assertTrue(self.client.get(reverse('parts:cart')).context['cart'].is_empty)
        self.add(self.pad)
        self.client.post(reverse('parts:cart_remove', args=[self.pad.pk]))
        self.assertTrue(self.client.get(reverse('parts:cart')).context['cart'].is_empty)

    def test_parts_that_disappear_are_pruned_with_a_message(self):
        self.add(self.disc)
        self.add(self.pad)
        Part.objects.filter(pk=self.disc.pk).update(availability=Part.Availability.UNAVAILABLE)
        PartImage.objects.filter(part=self.pad).delete()
        response = self.client.get(reverse('parts:cart'))
        self.assertTrue(response.context['cart'].is_empty)
        text = response.content.decode()
        self.assertIn('indisponible', text)
        self.assertIn("n&#x27;est plus proposée", text)

    def test_header_badge_shows_the_count_on_every_page(self):
        self.add(self.disc, 3)
        html = self.client.get(reverse('core:home')).content.decode()
        self.assertIn('data-cart-count', html)
        self.assertRegex(html, r'id="cart-badge"[^>]*>\s*3\s*<')


class CheckoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.disc = make_part('D-1', 'Disque de frein', price=40000)
        self.quote = make_part('Q-1', 'Étrier sur devis')
        self.zone = DeliveryZone.objects.create(name='Abidjan', fee=3000, lead_time='24 h')
        self.zone_nofee = DeliveryZone.objects.create(name='Intérieur du pays', order=2)
        self.client.post(reverse('parts:cart_add', args=[self.disc.pk]), {'quantity': 2})
        self.url = reverse('parts:checkout')

    def payload(self, **overrides):
        data = {'customer_type': 'particulier', 'full_name': 'Jean Kouadio', 'phone': '07 00 00 00 00',
                'email': '', 'company_name': '', 'reception': 'retrait', 'delivery_zone': '',
                'delivery_address': '', 'instructions': ''}
        data.update(overrides)
        return data

    def test_empty_cart_redirects_to_the_cart(self):
        self.client.post(reverse('parts:cart_remove', args=[self.disc.pk]))
        self.assertRedirects(self.client.get(self.url), reverse('parts:cart'), fetch_redirect_response=False)

    def test_form_lists_zones_with_fees(self):
        html = self.client.get(self.url).content.decode()
        for expected in ('Abidjan', '3', 'frais à confirmer', 'Retrait', 'Livraison', 'ne la confirme pas encore'):
            self.assertIn(expected, html)

    @override_settings(PARTS_NOTIFY_EMAILS=['pieces@example.com'])
    def test_pickup_order_is_created_with_a_frozen_copy_of_the_lines(self):
        response = self.client.post(self.url, self.payload(email='jean@example.com'))
        self.assertRedirects(response, reverse('parts:order_success'), fetch_redirect_response=False)
        order = PartOrder.objects.get()
        self.assertEqual(order.reference, f'DJP-CMD-{timezone.localdate().year}-0001')
        self.assertEqual((order.status, order.reception, order.phone), ('en_attente', 'retrait', '+225 0700000000'))
        self.assertEqual((order.subtotal, order.delivery_fee, order.total, order.has_unpriced_items), (80000, 0, 80000, False))
        self.assertTrue(order.total_is_final)
        line = order.lines.get()
        self.assertEqual((line.name, line.quantity, line.unit_price, line.line_total, line.part), ('Disque de frein', 2, 40000, 80000, self.disc))
        self.assertEqual(list(order.events.values_list('status', 'note')), [('en_attente', 'Commande reçue')])
        # Le prix change après coup : la commande garde le prix du moment.
        Part.objects.filter(pk=self.disc.pk).update(price=99999)
        self.assertEqual(order.lines.get().unit_price, 40000)
        # Panier vidé ; équipe et client prévenus.
        self.assertTrue(self.client.get(reverse('parts:cart')).context['cart'].is_empty)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['jean@example.com', 'pieces@example.com'])
        self.assertTrue(all(order.reference in m.subject for m in mail.outbox))

    def test_confirmation_page_is_shown_once_and_says_not_confirmed(self):
        self.client.post(self.url, self.payload())
        reference = PartOrder.objects.get().reference
        page = self.client.get(reverse('parts:order_success'))
        self.assertContains(page, reference)
        self.assertContains(page, 'pas encore confirmée')
        self.assertRedirects(self.client.get(reverse('parts:order_success')), reverse('parts:cart'), fetch_redirect_response=False)

    def test_delivery_needs_zone_and_address_and_applies_the_fee(self):
        response = self.client.post(self.url, self.payload(reception='livraison'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('delivery_zone', response.context['form'].errors)
        self.assertIn('delivery_address', response.context['form'].errors)
        self.assertEqual(PartOrder.objects.count(), 0)
        self.client.post(self.url, self.payload(reception='livraison', delivery_zone=self.zone.pk, delivery_address='Cocody, rue des Jardins'))
        order = PartOrder.objects.get()
        self.assertEqual((order.zone_name, order.delivery_fee, order.total, order.total_is_final), ('Abidjan', 3000, 83000, True))

    def test_zone_without_fee_keeps_the_total_estimated(self):
        self.client.post(self.url, self.payload(reception='livraison', delivery_zone=self.zone_nofee.pk, delivery_address='Bouaké'))
        order = PartOrder.objects.get()
        self.assertIsNone(order.delivery_fee)
        self.assertFalse(order.total_is_final)

    def test_company_needs_a_name_and_phone_must_be_valid(self):
        response = self.client.post(self.url, self.payload(customer_type='entreprise'))
        self.assertIn('company_name', response.context['form'].errors)
        response = self.client.post(self.url, self.payload(phone='123'))
        self.assertIn('phone', response.context['form'].errors)
        self.client.post(self.url, self.payload(customer_type='entreprise', company_name='Garage Auto'))
        self.assertEqual(PartOrder.objects.get().company_name, 'Garage Auto')

    def test_unpriced_parts_are_flagged_on_the_order(self):
        self.client.post(reverse('parts:cart_add', args=[self.quote.pk]), {'quantity': 1})
        self.client.post(self.url, self.payload())
        order = PartOrder.objects.get()
        self.assertTrue(order.has_unpriced_items)
        self.assertFalse(order.total_is_final)
        self.assertEqual(order.subtotal, 80000)  # seules les pièces chiffrées comptent
        self.assertIsNone(order.lines.get(name='Étrier sur devis').unit_price)

    def test_commission_follows_the_configured_rule_and_is_absent_by_default(self):
        self.client.post(self.url, self.payload())
        self.assertIsNone(PartOrder.objects.get().commission_amount)
        settings_ = PartsSettings.load()
        settings_.commission_type, settings_.commission_value = 'pourcentage', 5
        settings_.save()
        self.client.post(reverse('parts:cart_add', args=[self.disc.pk]), {'quantity': 2})
        self.client.post(self.url, self.payload())
        self.assertEqual(PartOrder.objects.order_by('-id').first().commission_amount, 4000)
        settings_.commission_type, settings_.commission_value = 'fixe', 1500
        settings_.save()
        self.assertEqual(settings_.commission_for(80000), 1500)
        self.assertIsNone(settings_.commission_for(0))

    def test_numbers_increase_and_rate_limit_applies(self):
        for i in range(5):
            self.client.post(reverse('parts:cart_add', args=[self.disc.pk]), {'quantity': 1})
            self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        self.assertEqual(list(PartOrder.objects.order_by('id').values_list('reference', flat=True))[-1][-4:], '0005')
        self.client.post(reverse('parts:cart_add', args=[self.disc.pk]), {'quantity': 1})
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trop de commandes')
        self.assertEqual(PartOrder.objects.count(), 5)

    def test_part_gone_between_cart_and_order_blocks_the_order(self):
        Part.objects.filter(pk=self.disc.pk).update(availability=Part.Availability.UNAVAILABLE)
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, reverse('parts:cart'), fetch_redirect_response=False)
        self.assertEqual(PartOrder.objects.count(), 0)


class TrackingAndStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.order = PartOrder.objects.create(full_name='Jean', phone='+225 0700000000', reception='retrait', subtotal=25000,
                                              delivery_fee=0)
        PartOrderEvent.objects.create(order=self.order, status='en_attente', note='Commande reçue')
        PartOrderEvent.objects.create(order=self.order, status='confirmee', note='Rappelé le client')

    def test_tracking_with_reference_and_phone(self):
        page = self.client.post(reverse('parts:track'), {'reference': self.order.reference.lower(), 'phone': '07 00 00 00 00'})
        self.assertContains(page, self.order.reference)
        self.assertContains(page, 'Confirmée')
        self.assertContains(page, 'Commande reçue')
        self.assertContains(page, 'Rappelé le client')

    def test_wrong_phone_or_unknown_reference_gives_the_same_generic_error(self):
        for data in ({'reference': self.order.reference, 'phone': '01 01 01 01 01'}, {'reference': 'DJP-CMD-2000-9999', 'phone': '07 00 00 00 00'}):
            page = self.client.post(reverse('parts:track'), data)
            self.assertContains(page, 'Aucune commande ne correspond')
            self.assertNotContains(page, 'Jean')

    def test_transitions_are_controlled(self):
        S = PartOrder.Status
        order = self.order
        self.assertEqual(order.next_statuses(), [S.CONFIRMED, S.CANCELLED, S.FAILED])
        order.status = S.PREPARING
        self.assertEqual(order.next_statuses(), [S.READY, S.CANCELLED])          # retrait
        order.reception = 'livraison'
        self.assertEqual(order.next_statuses(), [S.SHIPPING, S.CANCELLED])       # livraison
        for terminal in (S.DONE, S.CANCELLED):
            order.status = terminal
            self.assertEqual(order.next_statuses(), [])
        order.status = S.FAILED
        self.assertIn(S.PENDING, order.next_statuses())
        self.assertNotIn(S.DONE, PartOrder.TRANSITIONS[S.CANCELLED])

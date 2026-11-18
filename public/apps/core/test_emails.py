from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.parts.models import DeliveryZone, PartOrder, PartRequest, PartsSettings
from apps.parts.test_orders import make_part

from .models import ContactMessage, TransportRequest, TransportVehicleType
from .views import _notify_contact_message  # noqa: F401  (le chemin de la vue contact est testé via le client)

ADMIN = settings.ADMIN_SITE_URL
SITE = settings.SITE_URL


class BrandedBase(TestCase):
    def setUp(self):
        cache.clear()

    def branded(self, message):
        """Contrôles communs : texte + alternative HTML aux couleurs Djona ; renvoie le HTML."""
        self.assertEqual(len(message.alternatives), 1)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn(f'{SITE}/static/img/djona-group-logo-white.png', html)
        self.assertIn('<table', html)
        self.assertTrue(message.body.strip())  # la version texte reste présente
        self.assertNotIn('<table', message.body)
        return html


@override_settings(CONTACT_NOTIFY_EMAILS=['equipe@example.com'])
class ContactEmailTests(BrandedBase):
    def test_team_notification_is_branded_and_escapes_visitor_input(self):
        self.client.post(reverse('core:contact'), {
            'full_name': 'Jean Kouadio', 'phone': '0700000000', 'email': '', 'subject': 'achat',
            'message': '<script>alert(1)</script> Je cherche un SUV.\nMerci.',
        })
        message = mail.outbox[0]
        html = self.branded(message)
        contact = ContactMessage.objects.get()
        self.assertIn('Nouveau message de contact', html)
        self.assertIn('Jean Kouadio', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Merci.', html)
        self.assertIn(f'href="{ADMIN}/messages/{contact.pk}/"', html)


@override_settings(TRANSPORT_NOTIFY_EMAILS=['transport@example.com'])
class TransportEmailTests(BrandedBase):
    def test_team_notification_lists_the_request(self):
        vehicle_type = TransportVehicleType.objects.get(name='Camion-benne')
        self.client.post(reverse('core:transport'), {
            'last_name': 'Kouadio', 'first_name': 'Jean', 'phone': '0700000000', 'email': '', 'requester_type': 'particulier',
            'company_name': '', 'vehicle_type': vehicle_type.pk, 'quantity': '2',
            'loading_date': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'loading_place': 'Abidjan – Yopougon', 'delivery_place': 'Bamako – Mali', 'message': '',
        })
        html = self.branded(mail.outbox[0])
        request = TransportRequest.objects.get()
        for expected in (request.reference, 'Nouvelle demande de transport', 'Jean Kouadio', 'Bamako – Mali', '2 x Camion-benne'):
            self.assertIn(expected, html)
        self.assertIn(f'href="{ADMIN}/transport/"', html)
        self.assertNotIn('Message</p>', html)  # pas de bloc message quand il est vide


@override_settings(PARTS_NOTIFY_EMAILS=['pieces@example.com'])
class PartRequestEmailTests(BrandedBase):
    def test_team_notification_links_to_the_request(self):
        from apps.parts.views import _notify_part_request

        request = PartRequest.objects.create(
            full_name='Awa Traoré', phone='+225 0700000000', make='Kia', model='Rio', year=2018,
            part_name='Courroie de distribution', description='Urgent svp',
        )
        _notify_part_request(request)
        html = self.branded(mail.outbox[0])
        for expected in (request.reference, 'Nouvelle demande de pièce', 'Awa Traoré', 'Kia Rio 2018', 'Courroie de distribution', 'Urgent svp'):
            self.assertIn(expected, html)
        self.assertIn(f'href="{ADMIN}/pieces/demandes/{request.pk}/"', html)


@override_settings(PARTS_NOTIFY_EMAILS=['pieces@example.com'])
class OrderEmailTests(BrandedBase):
    def setUp(self):
        super().setUp()
        self.disc = make_part('D-1', 'Disque de frein', price=40000)
        self.quote = make_part('Q-1', 'Étrier sur devis')
        self.zone = DeliveryZone.objects.create(name='Abidjan', fee=3000, lead_time='24 h')
        self.nofee = DeliveryZone.objects.create(name='Intérieur du pays', order=2)
        self.client.post(reverse('parts:cart_add', args=[self.disc.pk]), {'quantity': 2})
        self.client.post(reverse('parts:cart_add', args=[self.quote.pk]), {'quantity': 1})

    def order(self, **overrides):
        data = {'customer_type': 'particulier', 'full_name': 'Jean Kouadio', 'phone': '07 00 00 00 00',
                'email': 'jean@example.com', 'company_name': '', 'reception': 'retrait', 'delivery_zone': '',
                'delivery_address': '', 'instructions': ''}
        data.update(overrides)
        self.client.post(reverse('parts:checkout'), data)
        return PartOrder.objects.get()

    def by_recipient(self, address):
        return next(m for m in mail.outbox if m.to == [address])

    def test_team_notification_has_lines_total_and_back_office_link(self):
        order = self.order(instructions='Appeler avant 17 h')
        html = self.branded(self.by_recipient('pieces@example.com'))
        for expected in ('Nouvelle commande de pièces', order.reference, 'Jean Kouadio', 'Disque de frein', 'Étrier sur devis',
                         'Sur demande', 'Sous-total', 'pièces sur devis', 'Instructions du client', 'Appeler avant 17 h'):
            self.assertIn(expected, html)
        self.assertIn(f'href="{ADMIN}/pieces/commandes/{order.pk}/"', html)

    def test_customer_confirmation_is_honest_and_links_to_tracking(self):
        order = self.order()
        html = self.branded(self.by_recipient('jean@example.com'))
        for expected in ('Nous avons bien reçu votre commande', order.reference, 'pas encore confirmée', 'Disque de frein',
                         'Sur demande', 'Retrait', 'Suivre ma commande'):
            self.assertIn(expected, html)
        self.assertNotIn('Frais de livraison', html)  # rien à livrer pour un retrait
        self.assertIn(f'href="{SITE}{reverse("parts:track")}"', html)
        # Rien d'inventé : sans conditions saisies par l'équipe, aucune ligne de retrait / paiement.
        self.assertNotIn('Lieu et conditions de retrait', html)
        self.assertNotIn('Modalités de paiement', html)

    def test_staff_entered_conditions_are_shown_to_the_customer(self):
        PartsSettings.objects.update_or_create(pk=1, defaults={'pickup_instructions': 'Angré 9e tranche', 'payment_terms': 'Paiement au retrait.'})
        self.order()
        html = self.by_recipient('jean@example.com').alternatives[0][0]
        for expected in ('Lieu et conditions de retrait', 'Angré 9e tranche', 'Modalités de paiement', 'Paiement au retrait.'):
            self.assertIn(expected, html)

    def test_delivery_fee_is_shown_or_flagged_to_confirm(self):
        self.order(reception='livraison', delivery_zone=self.nofee.pk, delivery_address='Bouaké, quartier Commerce')
        html = self.by_recipient('jean@example.com').alternatives[0][0]
        self.assertIn('Frais de livraison', html)
        self.assertIn('À confirmer', html)
        self.assertIn('Intérieur du pays', html)
        self.assertIn('Bouaké, quartier Commerce', html)
        self.assertNotIn('Lieu et conditions de retrait', html)

    def test_customer_name_is_escaped(self):
        self.order(full_name='<b>Jean</b>')
        html = self.by_recipient('jean@example.com').alternatives[0][0]
        self.assertIn('&lt;b&gt;Jean&lt;/b&gt;', html)
        self.assertNotIn('<b>Jean</b>', html)

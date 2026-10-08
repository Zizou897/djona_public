from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ContactMessage, SiteContact, TransportRequest, TransportVehicleType


class TransportRequestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.vehicle_type = TransportVehicleType.objects.get(name='Camion-benne')
        self.url = reverse('core:transport')

    def payload(self, **overrides):
        data = {
            'last_name': 'Kouadio',
            'first_name': 'Jean',
            'phone': '0700000000',
            'email': '',
            'requester_type': 'particulier',
            'company_name': '',
            'vehicle_type': self.vehicle_type.pk,
            'quantity': '2',
            'loading_date': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'loading_place': 'Abidjan – Yopougon',
            'delivery_place': 'Bamako – Mali',
            'message': '',
        }
        data.update(overrides)
        return data

    def test_page_renders_with_seeded_vehicle_types(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Transport &amp; <span')
        self.assertContains(response, 'Semi-remorque')

    @override_settings(TRANSPORT_NOTIFY_EMAILS=['transport@example.com'])
    def test_valid_submission_creates_request_with_reference_and_notifies(self):
        response = self.client.post(self.url, self.payload(), follow=True)
        year = timezone.localdate().year
        self.assertContains(response, f'DJ-TR-{year}-0001')
        request_obj = TransportRequest.objects.get()
        self.assertEqual(request_obj.status, TransportRequest.Status.NEW)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(request_obj.reference, mail.outbox[0].subject)

    def test_references_increment(self):
        self.client.post(self.url, self.payload())
        self.client.post(self.url, self.payload())
        refs = list(TransportRequest.objects.order_by('id').values_list('reference', flat=True))
        self.assertEqual([r.rsplit('-', 1)[1] for r in refs], ['0001', '0002'])

    def test_company_requires_company_name(self):
        response = self.client.post(self.url, self.payload(requester_type='entreprise'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TransportRequest.objects.count(), 0)
        self.assertContains(response, "Indiquez le nom de l&#x27;entreprise.")

    def test_company_name_dropped_for_individual(self):
        self.client.post(self.url, self.payload(company_name='ACME'))
        self.assertEqual(TransportRequest.objects.get().company_name, '')

    def test_past_loading_date_rejected(self):
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.client.post(self.url, self.payload(loading_date=past))
        self.assertEqual(TransportRequest.objects.count(), 0)

    def test_inactive_vehicle_type_rejected(self):
        TransportVehicleType.objects.filter(pk=self.vehicle_type.pk).update(is_active=False)
        self.client.post(self.url, self.payload())
        self.assertEqual(TransportRequest.objects.count(), 0)

    def test_success_page_without_reference_redirects(self):
        response = self.client.get(reverse('core:transport_success'))
        self.assertRedirects(response, self.url)


class ContactMessageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('core:contact')

    def payload(self, **overrides):
        data = {
            'full_name': 'Jean Kouadio',
            'phone': '0700000000',
            'email': '',
            'subject': 'achat',
            'message': 'Je cherche un SUV.',
        }
        data.update(overrides)
        return data

    def test_page_shows_official_contact_details(self):
        response = self.client.get(self.url)
        self.assertContains(response, '+225 01 41 60 27 53')
        self.assertContains(response, 'contact@djona.tech')
        self.assertContains(response, 'https://wa.me/2250141602753')
        self.assertNotContains(response, '0102030405')

    @override_settings(CONTACT_NOTIFY_EMAILS=['equipe@example.com'])
    def test_valid_submission_saves_and_notifies(self):
        response = self.client.post(self.url, self.payload(), follow=True)
        self.assertContains(response, 'Merci Jean Kouadio')
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.status, ContactMessage.Status.NEW)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Jean Kouadio', mail.outbox[0].subject)

    def test_missing_required_fields_rejected(self):
        response = self.client.post(self.url, self.payload(phone='', message=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_rate_limit(self):
        for _ in range(5):
            self.client.post(self.url, self.payload())
        self.client.post(self.url, self.payload())
        self.assertEqual(ContactMessage.objects.count(), 5)

    def test_success_page_without_submission_redirects(self):
        self.assertRedirects(self.client.get(reverse('core:contact_success')), self.url)


class SiteContactTests(TestCase):
    def test_page_reflects_backoffice_changes(self):
        SiteContact.objects.filter(pk=1).update(
            phone='+225 07 11 22 33 44', whatsapp='+225 05 55 66 77 88',
            email='support@djona.tech', address='Cocody Riviera 3', city='Abidjan',
        )
        response = self.client.get(reverse('core:contact'))
        self.assertContains(response, 'tel:+2250711223344')
        self.assertContains(response, 'https://wa.me/2250555667788')
        self.assertContains(response, 'support@djona.tech')
        self.assertContains(response, 'Cocody Riviera 3')
        self.assertNotContains(response, 'Angré 9ème tranche')

    def test_load_recreates_missing_row(self):
        SiteContact.objects.all().delete()
        self.assertEqual(SiteContact.load().email, 'contact@djona.tech')


class LegalPagesTests(TestCase):
    def test_pages_render_with_tabs_and_real_contact(self):
        for name in ('core:terms', 'core:privacy', 'core:seller_terms'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'aria-current="page"')
            self.assertContains(response, 'contact@djona.tech')
            self.assertContains(response, '3 octobre 2026')

    def test_unverified_claims_removed(self):
        privacy = self.client.get(reverse('core:privacy')).content.decode()
        self.assertNotIn('privacy@djona-auto.ci', privacy)
        self.assertNotIn('Palmeraie', privacy)
        sellers = self.client.get(reverse('core:seller_terms')).content.decode()
        self.assertNotIn('Séquestre', sellers)
        self.assertNotIn('experts mécaniques certifiés', sellers)
        self.assertIn('Au moins 3 photos', sellers)


class AskQuestionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('core:ask_question')

    def test_valid_question_saved_with_page(self):
        response = self.client.post(self.url, {
            'question': 'La voiture est-elle encore disponible ?', 'phone': '07 00 00 00 00',
            'page': 'https://djona.tech/vehicules/toyota-corolla-2022/',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['status'], 'success')
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.subject, ContactMessage.Subject.QUESTION)
        self.assertEqual(msg.phone, '+225 0700000000')
        self.assertIn('toyota-corolla-2022', msg.message)

    def test_invalid_phone_rejected(self):
        response = self.client.post(self.url, {'question': 'Une vraie question ?', 'phone': '12'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_modal_on_contact_and_question_not_in_contact_subjects(self):
        response = self.client.get(reverse('core:contact'))
        self.assertContains(response, 'id="ask-modal"')
        self.assertNotContains(response, '<option value="question"')


class FooterSocialLinksTests(TestCase):
    def test_only_filled_networks_are_shown(self):
        response = self.client.get(reverse('core:home'))
        self.assertNotContains(response, 'Djona sur Facebook')
        SiteContact.objects.filter(pk=1).update(
            facebook_url='https://www.facebook.com/djonagroup',
            linkedin_url='https://www.linkedin.com/company/djonagroup',
        )
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'href="https://www.facebook.com/djonagroup"')
        self.assertContains(response, 'Djona sur LinkedIn')
        self.assertNotContains(response, 'Djona sur Instagram')
        self.assertNotContains(response, 'Djona sur TikTok')


class HomeTruthTests(TestCase):
    def test_no_invented_figures_or_claims(self):
        content = self.client.get(reverse('core:home')).content.decode()
        for phrase in ('1450', 'Clients heureux', "Points d'inspection", "Heures d'accompagnement",
                       'inspecté par nos experts', 'inspectés et vérifiés par nos experts',
                       'milliers de vendeurs', 'première plateforme'):
            self.assertNotIn(phrase, content)

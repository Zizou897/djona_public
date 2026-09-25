from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TransportRequest, TransportVehicleType


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

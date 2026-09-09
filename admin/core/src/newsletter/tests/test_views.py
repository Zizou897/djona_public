from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from newsletter.models import NewsletterSubscriberMirror

User = get_user_model()


class NewsletterSubscriberViewsTest(TestCase):
    databases = {'default', 'public_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-newsletter', password='motdepasse', is_staff=True)
        self.subscriber = NewsletterSubscriberMirror.objects.using('public_db').create(
            email='abonne-test@exemple.ci', is_active=True, created_at=timezone.now(),
        )

    def tearDown(self):
        NewsletterSubscriberMirror.objects.using('public_db').filter(pk=self.subscriber.pk).delete()

    def test_liste_requiert_authentification_staff(self):
        response = self.client.get(reverse('newsletter_subscriber_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('newsletter_subscriber_liste')}")

    def test_liste_affiche_les_abonnes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('newsletter_subscriber_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'abonne-test@exemple.ci')

    def test_export_csv(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('newsletter_subscriber_export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(b'abonne-test@exemple.ci', response.content)

    def test_suppression_abonne(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('newsletter_subscriber_supprimer', args=[self.subscriber.pk]))
        self.assertRedirects(response, reverse('newsletter_subscriber_liste'))
        self.assertFalse(NewsletterSubscriberMirror.objects.using('public_db').filter(pk=self.subscriber.pk).exists())

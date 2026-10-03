from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contactmessages.models import ContactMessageMirror

User = get_user_model()


class ContactMessageViewsTest(TestCase):
    databases = {'default', 'public_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-contact', password='motdepasse', is_staff=True)
        self.msg = ContactMessageMirror.objects.using('public_db').create(
            full_name='Awa Traoré-Test', phone='0700000000', subject='vente',
            message='Je veux vendre ma Corolla.', created_at=timezone.now(),
        )

    def tearDown(self):
        ContactMessageMirror.objects.using('public_db').filter(pk=self.msg.pk).delete()

    def test_liste_requiert_authentification_staff(self):
        url = reverse('contact_message_liste')
        self.assertRedirects(self.client.get(url), f"{reverse('connexion_admin')}?next={url}")

    def test_liste_affiche_et_filtre(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('contact_message_liste'))
        self.assertContains(response, 'Awa Traoré-Test')
        self.assertContains(response, 'Vendre mon véhicule')
        response = self.client.get(reverse('contact_message_liste'), {'statut': 'traite'})
        self.assertNotContains(response, 'Awa Traoré-Test')

    def test_changement_de_statut(self):
        self.client.force_login(self.admin)
        url = reverse('contact_message_detail', args=[self.msg.pk])
        self.assertContains(self.client.get(url), 'Je veux vendre ma Corolla.')
        self.client.post(url, {'statut': 'traite'})
        self.assertEqual(ContactMessageMirror.objects.using('public_db').get(pk=self.msg.pk).status, 'traite')

    def test_statut_invalide_ignore(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('contact_message_detail', args=[self.msg.pk]), {'statut': 'nimporte'})
        self.assertEqual(ContactMessageMirror.objects.using('public_db').get(pk=self.msg.pk).status, 'nouveau')

    def test_question_sans_nom_affiche_visiteur(self):
        question = ContactMessageMirror.objects.using('public_db').create(
            full_name='', phone='+225 0700000000', subject='question',
            message='Disponible ?', created_at=timezone.now(),
        )
        try:
            self.client.force_login(self.admin)
            response = self.client.get(reverse('contact_message_detail', args=[question.pk]))
            self.assertContains(response, 'Visiteur')
            self.assertContains(response, 'Question (FAQ)')
        finally:
            ContactMessageMirror.objects.using('public_db').filter(pk=question.pk).delete()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from partners.models import PartnerMirror

User = get_user_model()

# Le plus petit PNG valide possible (1x1 pixel transparent) — nécessaire pour
# que la validation Pillow (forms.ImageField) accepte le fichier comme une
# vraie image.
PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00'
    b'\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class PartnerViewsTest(TestCase):
    databases = {'default', 'public_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-partners', password='motdepasse', is_staff=True)
        self.partner = PartnerMirror.objects.using('public_db').create(
            name='Banque Test', logo='partners/test.png', website_url='https://banque-test.ci', order=1,
        )

    def tearDown(self):
        PartnerMirror.objects.using('public_db').filter(pk=self.partner.pk).delete()

    def _logo(self):
        return SimpleUploadedFile('logo.png', PNG_1PX, content_type='image/png')

    def test_liste_requiert_authentification_staff(self):
        response = self.client.get(reverse('partner_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('partner_liste')}")

    def test_liste_affiche_les_partenaires(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('partner_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Banque Test')

    def test_creation_partenaire(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('partner_creer'), {
            'name': 'Assurance Test', 'logo': self._logo(), 'website_url': '', 'order': 0, 'publish': 'on',
        })
        self.assertRedirects(response, reverse('partner_liste'))
        self.assertTrue(PartnerMirror.objects.using('public_db').filter(name='Assurance Test').exists())
        PartnerMirror.objects.using('public_db').filter(name='Assurance Test').delete()

    def test_modification_partenaire(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('partner_modifier', args=[self.partner.pk]), {
            'name': 'Banque Test Renommée', 'website_url': '', 'order': 2,
        })
        self.assertRedirects(response, reverse('partner_liste'))
        self.partner.refresh_from_db(using='public_db')
        self.assertEqual(self.partner.name, 'Banque Test Renommée')
        self.assertFalse(self.partner.publish)

    def test_suppression_partenaire(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('partner_supprimer', args=[self.partner.pk]))
        self.assertRedirects(response, reverse('partner_liste'))
        self.assertFalse(PartnerMirror.objects.using('public_db').filter(pk=self.partner.pk).exists())

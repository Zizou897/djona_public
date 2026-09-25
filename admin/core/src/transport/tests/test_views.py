from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from transport.models import TransportRequestMirror, TransportVehicleTypeMirror

User = get_user_model()


class TransportViewsTest(TestCase):
    databases = {'default', 'public_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-transport', password='motdepasse', is_staff=True)
        self.type_ = TransportVehicleTypeMirror.objects.using('public_db').create(name='Camion test', order=99, is_active=True)
        self.demande = TransportRequestMirror.objects.using('public_db').create(
            reference='DJ-TR-2026-9999', last_name='Kouadio', first_name='Jean', phone='0700000000',
            requester_type='particulier', vehicle_type=self.type_, quantity='2',
            loading_date=timezone.localdate(), loading_place='Abidjan', delivery_place='Bamako',
            created_at=timezone.now(),
        )

    def tearDown(self):
        TransportRequestMirror.objects.using('public_db').all().delete()
        TransportVehicleTypeMirror.objects.using('public_db').filter(pk=self.type_.pk).delete()

    def test_liste_requiert_authentification_staff(self):
        url = reverse('transport_demande_liste')
        self.assertRedirects(self.client.get(url), f"{reverse('connexion_admin')}?next={url}")

    def test_liste_affiche_les_demandes_et_filtre_par_statut(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('transport_demande_liste'))
        self.assertContains(response, 'DJ-TR-2026-9999')
        response = self.client.get(reverse('transport_demande_liste'), {'statut': 'traitee'})
        self.assertNotContains(response, 'DJ-TR-2026-9999')

    def test_changement_de_statut(self):
        self.client.force_login(self.admin)
        url = reverse('transport_demande_detail', args=[self.demande.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'statut': 'en_traitement'})
        self.assertEqual(TransportRequestMirror.objects.using('public_db').get(pk=self.demande.pk).status, 'en_traitement')

    def test_statut_invalide_ignore(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('transport_demande_detail', args=[self.demande.pk]), {'statut': 'nimporte'})
        self.assertEqual(TransportRequestMirror.objects.using('public_db').get(pk=self.demande.pk).status, 'nouvelle')

    def test_ajout_et_bascule_type_vehicule(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('transport_type_liste'), {'name': 'Frigorifique', 'order': 5})
        created = TransportVehicleTypeMirror.objects.using('public_db').get(name='Frigorifique')
        self.client.post(reverse('transport_type_basculer', args=[created.pk]))
        created.refresh_from_db(using='public_db')
        self.assertFalse(created.is_active)

    def test_doublon_type_refuse(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('transport_type_liste'), {'name': 'camion TEST', 'order': 1})
        self.assertContains(response, 'Ce type existe déjà.')

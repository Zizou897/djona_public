from django.test import TestCase

from moderation.models import AnnonceMirror, AnnoncePhotoMirror, CompteVendeur


class AnnonceMirrorTest(TestCase):
    databases = {'vendor_db'}

    def setUp(self):
        self.vendeur = CompteVendeur.objects.using('vendor_db').create(
            email='mirror-vendeur@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )

    def tearDown(self):
        AnnoncePhotoMirror.objects.using('vendor_db').filter(annonce__vendeur=self.vendeur).delete()
        AnnonceMirror.objects.using('vendor_db').filter(vendeur=self.vendeur).delete()
        CompteVendeur.objects.using('vendor_db').filter(email='mirror-vendeur@exemple.ci').delete()

    def test_lit_les_annonces_reelles(self):
        annonce = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant='essence', boite_vitesses='automatique',
            couleur='Gris', description='Très bon état.', statut=AnnonceMirror.Statut.EN_ATTENTE,
            created_at='2026-08-27T10:00:00Z', update_at='2026-08-27T10:00:00Z',
        )
        AnnoncePhotoMirror.objects.using('vendor_db').create(annonce=annonce, image='annonces/test.jpg', ordre=0)

        relue = AnnonceMirror.objects.using('vendor_db').get(pk=annonce.pk)
        self.assertEqual(relue.marque, 'Toyota')
        self.assertEqual(relue.photos.count(), 1)

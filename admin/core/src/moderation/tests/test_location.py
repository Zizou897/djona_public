import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from moderation.forms import AnnonceAdminForm
from moderation.models import AnnonceMirror, AnnoncePhotoMirror, CompteVendeur

User = get_user_model()


def donnees(**surcharge):
    data = {
        'marque': 'Toyota', 'modele': 'Prado', 'annee': 2020, 'kilometrage': 58000, 'carburant': 'diesel',
        'boite_vitesses': 'automatique', 'couleur': 'Blanc', 'etat': 'occasion', 'ville': 'abidjan_cocody',
        'description': 'Véhicule officiel Djona.',
    }
    data.update(surcharge)
    return data


def photo(nom):
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'white').save(buffer, 'PNG')
    return SimpleUploadedFile(nom, buffer.getvalue(), content_type='image/png')


class FormulaireLocationAdminTest(TestCase):
    def test_vente_exige_le_prix_et_efface_les_champs_de_location(self):
        form = AnnonceAdminForm(donnees(type_annonce='vente', prix_jour='30000'))
        self.assertFalse(form.is_valid())
        self.assertIn('prix', form.errors)
        form = AnnonceAdminForm(donnees(prix='32500000', prix_jour='30000', caution='1'))
        self.assertTrue(form.is_valid(), form.errors)
        annonce = form.save(commit=False)
        self.assertEqual((annonce.type_annonce, annonce.prix, annonce.prix_jour, annonce.caution), ('vente', 32500000, None, None))

    def test_location_demande_au_moins_une_periode(self):
        form = AnnonceAdminForm(donnees(type_annonce='location', caution='300000'))
        self.assertFalse(form.is_valid())
        self.assertIn('prix_jour', form.errors)
        for champ in ('prix_jour', 'prix_semaine', 'prix_mois'):
            form = AnnonceAdminForm(donnees(type_annonce='location', **{champ: '50000'}))
            self.assertTrue(form.is_valid(), (champ, form.errors))
            annonce = form.save(commit=False)
            self.assertEqual(annonce.prix, 0)
            self.assertTrue(annonce.est_location)
            self.assertTrue(annonce.resume_prix.endswith('FCFA / ' + champ.replace('prix_', '')))


class CreationLocationAdminTest(TestCase):
    databases = {'default', 'vendor_db', 'public_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-loc', password='motdepasse', is_staff=True)
        self.systeme = CompteVendeur.objects.using('vendor_db').create(
            email='officiel@djona.tech', nom='Djona', prenom='Officiel', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.client.force_login(self.admin)

    def tearDown(self):
        AnnoncePhotoMirror.objects.using('vendor_db').filter(annonce__vendeur=self.systeme).delete()
        AnnonceMirror.objects.using('vendor_db').filter(vendeur=self.systeme).delete()
        CompteVendeur.objects.using('vendor_db').filter(pk=self.systeme.pk).delete()

    def test_creation_d_une_location_publiee_et_affichage(self):
        with override_settings(MEDIA_ROOT=self.media):
            reponse = self.client.post(reverse('annonce_creer_admin'), {
                **donnees(), 'type_annonce': 'location', 'prix_jour': '60000', 'prix_semaine': '350000',
                'caution': '500000', 'photos': [photo(f'p{i}.png') for i in range(3)],
            })
        self.assertRedirects(reponse, reverse('annonce_moderation_liste'))
        annonce = AnnonceMirror.objects.using('vendor_db').get(vendeur=self.systeme)
        self.assertEqual((annonce.type_annonce, annonce.prix, annonce.prix_jour, annonce.prix_semaine, annonce.prix_mois, annonce.caution),
                         ('location', 0, 60000, 350000, None, 500000))
        self.assertEqual(annonce.statut, AnnonceMirror.Statut.PUBLIEE)
        detail = self.client.get(reverse('annonce_moderation_detail', args=[annonce.pk])).content.decode()
        self.assertIn('/ jour', detail)
        self.assertIn('/ semaine', detail)
        self.assertNotIn('/ mois', detail)
        self.assertIn('caution', detail)
        liste = self.client.get(reverse('annonce_moderation_liste')).content.decode()
        self.assertIn('FCFA / jour', liste)

    def test_formulaire_de_creation_propose_vente_ou_location(self):
        page = self.client.get(reverse('annonce_creer_admin')).content.decode()
        for attendu in ('À vendre', 'À louer', 'Tarif par jour', 'Tarif par semaine', 'Tarif par mois', 'Caution'):
            self.assertIn(attendu, page)

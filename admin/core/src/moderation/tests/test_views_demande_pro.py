from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from moderation.models import CompteVendeur, DemandePassageProMirror, ProfilMirror

User = get_user_model()


class DemandeProViewsTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin-demandes', password='motdepasse', is_staff=True)
        self.vendeur = CompteVendeur.objects.using('vendor_db').create(
            email='demande-pro@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-09-01T10:00:00Z', password='inutilise',
        )
        self.demande = self.creer_demande()
        self.client.force_login(self.admin)

    def creer_demande(self, **overrides):
        donnees = {
            'utilisateur': self.vendeur, 'raison_sociale': 'Ivoire Auto SARL',
            'numero_rccm': 'CI-ABJ-2026-B-12345', 'adresse': 'Marcory, Abidjan',
            'justificatif_rccm': 'justificatifs/rccm.pdf', 'message': 'Concession de 30 véhicules.',
            'statut': DemandePassageProMirror.Statut.EN_ATTENTE, 'created_at': timezone.now(),
        }
        donnees.update(overrides)
        return DemandePassageProMirror.objects.using('vendor_db').create(**donnees)

    def test_liste_requiert_un_compte_staff(self):
        self.client.logout()
        response = self.client.get(reverse('demande_pro_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('demande_pro_liste')}")

    def test_liste_affiche_les_demandes_en_attente_en_premier(self):
        self.creer_demande(raison_sociale='Ancienne SARL', statut=DemandePassageProMirror.Statut.REFUSEE)
        response = self.client.get(reverse('demande_pro_liste'))
        self.assertEqual(response.status_code, 200)
        contenu = response.content.decode()
        self.assertLess(contenu.index('Ivoire Auto SARL'), contenu.index('Ancienne SARL'))
        self.assertEqual(response.context['nb_en_attente'], 1)

    def test_fiche_affiche_le_dossier(self):
        response = self.client.get(reverse('demande_pro_detail', args=[self.demande.pk]))
        self.assertContains(response, 'CI-ABJ-2026-B-12345')
        self.assertContains(response, 'Concession de 30 véhicules.')
        self.assertContains(response, reverse('demande_pro_accepter', args=[self.demande.pk]))

    def test_accepter_passe_le_compte_pro_et_verifie_l_entreprise(self):
        ProfilMirror.objects.using('vendor_db').create(user_id=self.vendeur.pk)
        response = self.client.post(reverse('demande_pro_accepter', args=[self.demande.pk]))
        self.assertRedirects(response, reverse('demande_pro_liste'))

        self.vendeur.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur.type_compte, CompteVendeur.TypeCompte.PROFESSIONNEL)
        profil = ProfilMirror.objects.using('vendor_db').get(user_id=self.vendeur.pk)
        self.assertEqual(profil.raison_sociale, 'Ivoire Auto SARL')
        self.assertEqual(profil.numero_rccm, 'CI-ABJ-2026-B-12345')
        self.assertEqual(profil.justificatif_rccm.name, 'justificatifs/rccm.pdf')
        self.assertTrue(profil.entreprise_verifiee)
        self.demande.refresh_from_db(using='vendor_db')
        self.assertEqual(self.demande.statut, DemandePassageProMirror.Statut.ACCEPTEE)
        self.assertIsNotNone(self.demande.traitee_le)

    def test_accepter_cree_le_profil_s_il_manque(self):
        self.client.post(reverse('demande_pro_accepter', args=[self.demande.pk]))
        self.assertTrue(
            ProfilMirror.objects.using('vendor_db').filter(user_id=self.vendeur.pk, entreprise_verifiee=True).exists()
        )

    def test_refuser_exige_un_motif(self):
        self.client.post(reverse('demande_pro_refuser', args=[self.demande.pk]), {'motif_refus': '  '})
        self.demande.refresh_from_db(using='vendor_db')
        self.assertEqual(self.demande.statut, DemandePassageProMirror.Statut.EN_ATTENTE)

    def test_refuser_enregistre_le_motif_sans_changer_le_compte(self):
        response = self.client.post(
            reverse('demande_pro_refuser', args=[self.demande.pk]), {'motif_refus': 'Justificatif illisible'},
        )
        self.assertRedirects(response, reverse('demande_pro_liste'))
        self.demande.refresh_from_db(using='vendor_db')
        self.assertEqual(self.demande.statut, DemandePassageProMirror.Statut.REFUSEE)
        self.assertEqual(self.demande.motif_refus, 'Justificatif illisible')
        self.vendeur.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur.type_compte, CompteVendeur.TypeCompte.PARTICULIER)

    def test_une_demande_deja_traitee_ne_peut_plus_etre_acceptee(self):
        self.demande.statut = DemandePassageProMirror.Statut.REFUSEE
        self.demande.save(using='vendor_db', update_fields=['statut'])
        self.client.post(reverse('demande_pro_accepter', args=[self.demande.pk]))
        self.vendeur.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur.type_compte, CompteVendeur.TypeCompte.PARTICULIER)

    def test_traitement_refuse_get(self):
        response = self.client.get(reverse('demande_pro_accepter', args=[self.demande.pk]))
        self.assertEqual(response.status_code, 405)

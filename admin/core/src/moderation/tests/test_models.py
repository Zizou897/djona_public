from django.test import TestCase

from moderation.models import CompteVendeur


class CompteVendeurTest(TestCase):
    databases = {'vendor_db'}

    def test_lit_les_comptes_vendeur_reels(self):
        CompteVendeur.objects.using('vendor_db').create(
            email='test-moderation@exemple.ci',
            nom='Test',
            prenom='Moderation',
            telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.EN_ATTENTE,
            is_active=True,
            date_joined='2026-08-27T10:00:00Z',
            password='inutilise',
        )
        compte = CompteVendeur.objects.using('vendor_db').get(email='test-moderation@exemple.ci')
        self.assertEqual(compte.prenom, 'Moderation')
        self.assertEqual(compte.statut_compte, CompteVendeur.StatutCompte.EN_ATTENTE)

    def test_changement_de_statut_persiste(self):
        compte = CompteVendeur.objects.using('vendor_db').create(
            email='test-moderation-update@exemple.ci',
            nom='Test',
            prenom='Moderation',
            telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.EN_ATTENTE,
            is_active=True,
            date_joined='2026-08-27T10:00:00Z',
            password='inutilise',
        )

        compte.statut_compte = CompteVendeur.StatutCompte.ACTIF
        compte.save(using='vendor_db', update_fields=['statut_compte'])

        compte_relu = CompteVendeur.objects.using('vendor_db').get(email='test-moderation-update@exemple.ci')
        self.assertEqual(compte_relu.statut_compte, CompteVendeur.StatutCompte.ACTIF)

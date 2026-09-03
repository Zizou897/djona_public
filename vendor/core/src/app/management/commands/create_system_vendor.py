from django.core.management.base import BaseCommand

from app.models import Utilisateur

SYSTEM_VENDOR_EMAIL = 'officiel@djona.tech'


class Command(BaseCommand):
    help = (
        "Crée (si absent) le compte vendeur système auquel sont rattachées les "
        "annonces créées directement depuis le dashboard admin."
    )

    def handle(self, *args, **options):
        if Utilisateur.objects.filter(email=SYSTEM_VENDOR_EMAIL).exists():
            self.stdout.write(self.style.WARNING(f'{SYSTEM_VENDOR_EMAIL} existe déjà — rien à faire.'))
            return

        Utilisateur.objects.create_user(
            email=SYSTEM_VENDOR_EMAIL,
            password=None,  # set_password(None) -> mot de passe inutilisable, compte non-connectable
            nom='Djona',
            prenom='Officiel',
            telephone='0000000000',
            type_compte=Utilisateur.TypeCompte.PROFESSIONNEL,
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.stdout.write(self.style.SUCCESS(f'Compte système {SYSTEM_VENDOR_EMAIL} créé.'))

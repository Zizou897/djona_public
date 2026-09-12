from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone

from .managers import UtilisateurManager

telephone_validator = RegexValidator(
    regex=r'^\d{8,10}$',
    message='Le numéro doit contenir entre 8 et 10 chiffres, sans le préfixe pays.',
)


class Convention(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)
    publish = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    class StatutCompte(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'

    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10, validators=[telephone_validator])
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices, default=TypeCompte.PARTICULIER)
    statut_compte = models.CharField(max_length=20, choices=StatutCompte.choices, default=StatutCompte.EN_ATTENTE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UtilisateurManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom', 'telephone']

    class Meta:
        db_table = 'vendeur_utilisateurs'

    def __str__(self):
        return f'{self.prenom} {self.nom} ({self.email})'

    def get_full_name(self):
        return f'{self.prenom} {self.nom}'.strip()

    def get_short_name(self):
        return self.prenom

    @property
    def avatar_url(self):
        try:
            if hasattr(self, 'profil') and self.profil.avatar:
                return self.profil.avatar.url
        except Exception:
            return None
        return None

    @property
    def is_pro_ou_membre(self):
        """True pour le titulaire d'un compte entreprise, ou pour un compte
        rattaché en tant que membre actif de l'équipe d'un titulaire —
        détermine quel tableau de bord s'affiche après connexion."""
        if self.type_compte == self.TypeCompte.PROFESSIONNEL:
            return True
        rattachement = getattr(self, 'rattachement_pro', None)
        return bool(rattachement and rattachement.actif)

    @property
    def compte_stock(self):
        """Le compte dont les annonces doivent être gérées par cet
        utilisateur : lui-même, sauf s'il s'agit d'un membre d'équipe
        rattaché à un compte pro — auquel cas c'est le stock du titulaire."""
        rattachement = getattr(self, 'rattachement_pro', None)
        if rattachement is not None and rattachement.actif:
            return rattachement.compte_pro
        return self


class Profil(models.Model):
    class Ville(models.TextChoices):
        ABIDJAN_COCODY = 'abidjan_cocody', 'Abidjan, Cocody'
        ABIDJAN_MARCORY = 'abidjan_marcory', 'Abidjan, Marcory'
        ABIDJAN_KOUMASSI = 'abidjan_koumassi', 'Abidjan, Koumassi'
        YAMOUSSOUKRO = 'yamoussoukro', 'Yamoussoukro'
        BOUAKE = 'bouake', 'Bouaké'

    class Langue(models.TextChoices):
        FRANCAIS = 'fr', 'Français'
        ANGLAIS = 'en', 'English'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profil',
    )
    ville = models.CharField(max_length=30, choices=Ville.choices, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    # Utilisé comme logo sur la page vitrine publique quand type_compte est
    # 'professionnel' (Utilisateur.type_compte) — sinon comme photo de profil
    # classique. Pas de champ logo séparé : un seul et même emplacement image.
    raison_sociale = models.CharField(
        'raison sociale', max_length=150, blank=True,
        help_text="Nom de l'entreprise, affiché sur la page vitrine publique (comptes professionnels).",
    )
    numero_rccm = models.CharField(
        'numéro RCCM', max_length=50, blank=True,
        help_text='Registre du Commerce et du Crédit Mobilier — sert de base à la vérification du compte entreprise.',
    )
    justificatif_rccm = models.FileField(
        'justificatif RCCM', upload_to='justificatifs/', blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text='Copie du registre de commerce (PDF ou image) — nécessaire pour obtenir le statut « Entreprise vérifiée ».',
    )
    adresse = models.CharField('adresse du showroom', max_length=255, blank=True)
    entreprise_verifiee = models.BooleanField(
        'entreprise vérifiée', default=False,
        help_text="Passe à True après validation du justificatif RCCM par l'équipe Djona (comptes professionnels).",
    )
    two_factor_enabled = models.BooleanField(default=False)
    langue = models.CharField(max_length=2, choices=Langue.choices, default=Langue.FRANCAIS)
    notif_email = models.BooleanField(default=True)
    notif_whatsapp = models.BooleanField(default=True)

    def __str__(self):
        return f'Profil de {self.user}'


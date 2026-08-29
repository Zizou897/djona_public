from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
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
    two_factor_enabled = models.BooleanField(default=False)
    langue = models.CharField(max_length=2, choices=Langue.choices, default=Langue.FRANCAIS)
    notif_email = models.BooleanField(default=True)
    notif_whatsapp = models.BooleanField(default=True)

    def __str__(self):
        return f'Profil de {self.user}'


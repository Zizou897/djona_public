from django.conf import settings
from django.db import models

class Convention(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)
    publish = models.BooleanField(default=False)

    class Meta:
        abstract = True


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
    telephone = models.CharField(max_length=30, blank=True)
    ville = models.CharField(max_length=30, choices=Ville.choices, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False)
    langue = models.CharField(max_length=2, choices=Langue.choices, default=Langue.FRANCAIS)
    notif_email = models.BooleanField(default=True)
    notif_whatsapp = models.BooleanField(default=True)

    def __str__(self):
        return f'Profil de {self.user}'

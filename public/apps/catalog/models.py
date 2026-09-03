from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify


class Convention(models.Model):
    """Base abstraite pour les modèles publiables (cf. AGENTS.md §5)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    publish = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Seller(models.Model):
    """Vitrine publique d'un vendeur — synchronisée en lecture seule depuis
    vendor.app.Utilisateur/Profil (voir apps.vendor_sync.management.commands
    .sync_validated_annonces). Ce projet ne fait qu'écrire ici via la
    synchro : jamais créé/modifié par une action utilisateur publique.
    """

    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    source_vendeur_id = models.PositiveIntegerField(unique=True)
    first_name = models.CharField('prénom', max_length=100)
    last_name = models.CharField('nom', max_length=100)
    phone = models.CharField('téléphone', max_length=10, blank=True)
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices, default=TypeCompte.PARTICULIER)
    company_name = models.CharField('raison sociale', max_length=150, blank=True)
    logo = models.ImageField('logo', upload_to='sellers/', blank=True, null=True)
    member_since = models.DateTimeField('membre depuis')
    slug = models.SlugField('slug', max_length=180, unique=True, blank=True)

    class Meta:
        verbose_name = 'vendeur'
        verbose_name_plural = 'vendeurs'

    def __str__(self):
        return self.display_name

    @property
    def is_professional(self):
        return self.type_compte == self.TypeCompte.PROFESSIONNEL

    @property
    def display_name(self):
        if self.is_professional and self.company_name:
            return self.company_name
        return f'{self.first_name} {self.last_name}'.strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.display_name) or f'vendeur-{self.source_vendeur_id}'
            slug = base_slug
            i = 1
            while Seller.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                i += 1
                slug = f'{base_slug}-{i}'
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('catalog:seller_detail', kwargs={'slug': self.slug})


class Vehicle(Convention):
    class FuelType(models.TextChoices):
        ESSENCE = 'essence', 'Essence'
        DIESEL = 'diesel', 'Diesel'
        HYBRIDE = 'hybride', 'Hybride'
        ELECTRIQUE = 'electrique', 'Électrique'

    class Transmission(models.TextChoices):
        AUTOMATIQUE = 'automatique', 'Automatique'
        MANUELLE = 'manuelle', 'Manuelle'

    class Condition(models.TextChoices):
        NEUF = 'neuf', 'Neuf'
        OCCASION = 'occasion', 'Occasion'

    brand = models.CharField('marque', max_length=80)
    model_name = models.CharField('modèle', max_length=120)
    year = models.PositiveSmallIntegerField('année')
    price = models.PositiveBigIntegerField('prix (FCFA)')
    mileage = models.PositiveIntegerField('kilométrage (km)')
    fuel_type = models.CharField('carburant', max_length=20, choices=FuelType.choices, default=FuelType.ESSENCE)
    transmission = models.CharField('transmission', max_length=20, choices=Transmission.choices, default=Transmission.AUTOMATIQUE)
    city = models.CharField('ville', max_length=120)
    condition = models.CharField('état', max_length=20, choices=Condition.choices, default=Condition.OCCASION)
    slug = models.SlugField('slug', max_length=160, unique=True, blank=True)
    is_verified = models.BooleanField('inspecté par Djona', default=False)
    source_annonce_id = models.PositiveIntegerField(
        'id annonce d\'origine', null=True, blank=True, unique=True,
        help_text='Référence vers annonces.id (djona_vendor) si ce véhicule provient de la synchro back-office.',
    )
    description = models.TextField('description', blank=True)
    seller = models.ForeignKey(
        Seller, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicles',
    )

    class Meta:
        verbose_name = 'véhicule'
        verbose_name_plural = 'véhicules'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.brand} {self.model_name} ({self.year})'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f'{self.brand}-{self.model_name}-{self.year}')
            slug = base_slug
            i = 1
            while Vehicle.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                i += 1
                slug = f'{base_slug}-{i}'
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('catalog:detail', kwargs={'slug': self.slug})


class VehicleImage(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField('image', upload_to='vehicles/')
    order = models.PositiveSmallIntegerField('ordre', default=0)

    class Meta:
        verbose_name = 'image véhicule'
        verbose_name_plural = 'images véhicule'
        ordering = ['order']

    def __str__(self):
        return f'Image #{self.order} — {self.vehicle}'


class Favorite(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='favorited_by')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'favori'
        verbose_name_plural = 'favoris'
        constraints = [
            models.UniqueConstraint(fields=['user', 'vehicle'], condition=Q(user__isnull=False), name='unique_user_favorite'),
            models.UniqueConstraint(fields=['session_key', 'vehicle'], condition=~Q(session_key=''), name='unique_session_favorite'),
        ]

    def __str__(self):
        return f'{self.vehicle} — {self.user or self.session_key}'

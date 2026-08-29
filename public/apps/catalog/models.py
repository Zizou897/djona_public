from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify


class Convention(models.Model):
    """Base abstraite pour les modèles publiables (cf. AGENTS.md §5)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    publish = models.BooleanField(default=False)

    class Meta:
        abstract = True


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
    description = models.TextField('description', blank=True)

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

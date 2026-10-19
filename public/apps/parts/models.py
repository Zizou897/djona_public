import re

from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.imaging import optimize_field


def normalize_reference(value):
    """« 04465-33450 » et « 0446533450 » désignent la même référence : on
    compare sans séparateurs ni casse."""
    return re.sub(r'[^0-9A-Z]', '', (value or '').upper())


class PartCategory(models.Model):
    """Famille de pièces (Moteur, Freinage…). Administrable depuis le back-office
    (admin/core/src/parts/) ; le public ne fait que lire.
    """

    name = models.CharField('nom', max_length=80, unique=True)
    icon = models.CharField('icône (Material Symbols)', max_length=40, default='settings')
    order = models.PositiveIntegerField('ordre', default=0)
    is_active = models.BooleanField('visible', default=True)

    class Meta:
        verbose_name = 'catégorie de pièces'
        verbose_name_plural = 'catégories de pièces'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Part(models.Model):
    """Pièce détachée du catalogue Djona Parts.

    Les champs facultatifs (état, prix, garantie, délai) restent vides tant que
    l'information n'est pas connue : le site affiche alors « sur demande » ou
    « à confirmer » plutôt qu'une valeur inventée. Créée et modifiée depuis le
    back-office (saisie ou import CSV) ; le public ne fait que lire.
    """

    class Condition(models.TextChoices):
        NEW = 'neuf', 'Neuf'
        REFURBISHED = 'reconditionne', 'Reconditionné'
        USED = 'occasion', 'Occasion'

    class Availability(models.TextChoices):
        AVAILABLE = 'disponible', 'Disponible'
        UNAVAILABLE = 'indisponible', 'Indisponible'
        TO_CONFIRM = 'a_confirmer', 'À confirmer'

    reference = models.CharField('référence Djona', max_length=60, unique=True)
    name = models.CharField('désignation', max_length=150)
    manufacturer_reference = models.CharField('référence fabricant (OEM)', max_length=80, blank=True)
    brand = models.CharField('marque de la pièce', max_length=80, blank=True)
    category = models.ForeignKey(PartCategory, verbose_name='catégorie', on_delete=models.PROTECT, related_name='parts')
    condition = models.CharField('état', max_length=20, choices=Condition.choices, blank=True)
    price = models.PositiveIntegerField('prix (FCFA)', null=True, blank=True)
    availability = models.CharField('disponibilité', max_length=20, choices=Availability.choices, default=Availability.TO_CONFIRM)
    warranty = models.CharField('garantie', max_length=150, blank=True)
    lead_time = models.CharField('délai estimé', max_length=100, blank=True)
    description = models.TextField('description', blank=True)
    is_featured = models.BooleanField('pièce populaire', default=False)
    is_active = models.BooleanField('visible sur le site', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'pièce détachée'
        verbose_name_plural = 'pièces détachées'
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return f'{self.name} ({self.reference})'

    @property
    def slug(self):
        return slugify(self.name) or 'piece'

    def get_absolute_url(self):
        return reverse('parts:detail', kwargs={'pk': self.pk, 'slug': self.slug})


class PartImage(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField('image', upload_to='parts/', max_length=255)
    order = models.PositiveSmallIntegerField('ordre', default=0)

    class Meta:
        verbose_name = 'image de pièce'
        verbose_name_plural = 'images de pièces'
        ordering = ['order', 'id']

    def __str__(self):
        return f'Image #{self.order} — {self.part_id}'


class PartCompatibility(models.Model):
    """Une ligne = un véhicule sur lequel la pièce est montable. Modèle vide =
    toute la marque ; années vides = toutes les années."""

    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='compatibilities')
    make = models.CharField('marque', max_length=60)
    model = models.CharField('modèle', max_length=80, blank=True)
    year_from = models.PositiveSmallIntegerField('à partir de', null=True, blank=True)
    year_to = models.PositiveSmallIntegerField("jusqu'à", null=True, blank=True)
    engine = models.CharField('motorisation', max_length=80, blank=True)

    class Meta:
        verbose_name = 'compatibilité'
        verbose_name_plural = 'compatibilités'
        ordering = ['make', 'model', 'year_from']

    def __str__(self):
        return self.label

    @property
    def label(self):
        text = f'{self.make} {self.model}'.strip()
        if self.year_from and self.year_to and self.year_from != self.year_to:
            text += f' ({self.year_from}–{self.year_to})'
        elif self.year_from and self.year_to:
            text += f' ({self.year_from})'
        elif self.year_from:
            text += f' (depuis {self.year_from})'
        elif self.year_to:
            text += f" (jusqu'à {self.year_to})"
        if self.engine:
            text += f' — {self.engine}'
        return text


class PartRequest(models.Model):
    """Demande « Je ne trouve pas ma pièce » (ou demande d'une pièce précise du
    catalogue). Créée par le formulaire public ; le back-office la traite :
    recherche de la pièce, proposition (prix, délai) puis suite donnée.
    """

    class Status(models.TextChoices):
        NEW = 'nouvelle', 'Nouvelle demande'
        SEARCHING = 'en_recherche', 'En recherche'
        PROPOSED = 'proposition_envoyee', 'Proposition envoyée'
        ACCEPTED = 'acceptee', 'Acceptée par le client'
        DECLINED = 'refusee', 'Refusée par le client'
        NO_FOLLOW_UP = 'sans_suite', 'Sans suite'

    reference = models.CharField('numéro de demande', max_length=20, unique=True, editable=False)
    full_name = models.CharField('nom et prénom', max_length=150)
    phone = models.CharField('téléphone / WhatsApp', max_length=30)
    make = models.CharField('marque du véhicule', max_length=60)
    model = models.CharField('modèle', max_length=80)
    year = models.PositiveSmallIntegerField('année')
    engine = models.CharField('motorisation', max_length=80, blank=True)
    part_name = models.CharField('pièce recherchée', max_length=150)
    part_reference = models.CharField('référence', max_length=80, blank=True)
    description = models.TextField('description du besoin')
    photo = models.ImageField('photo', upload_to='part_requests/', max_length=255, blank=True)
    part = models.ForeignKey(Part, verbose_name='pièce du catalogue', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='requests')
    status = models.CharField('statut', max_length=30, choices=Status.choices, default=Status.NEW)
    proposed_price = models.PositiveIntegerField('prix proposé (FCFA)', null=True, blank=True)
    proposed_lead_time = models.CharField('délai proposé', max_length=100, blank=True)
    internal_note = models.TextField('note interne', blank=True)
    created_at = models.DateTimeField('date de la demande', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'demande de pièce'
        verbose_name_plural = 'demandes de pièces'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        self.photo = optimize_field(self.photo)
        if self.reference:
            return super().save(*args, **kwargs)
        # Deux soumissions simultanées peuvent viser le même numéro : on retente.
        for attempt in range(5):
            self.reference = self._next_reference()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if attempt == 4:
                    raise
                self.reference = ''

    @classmethod
    def _next_reference(cls):
        prefix = f'DJ-PC-{timezone.localdate().year}-'
        last = cls.objects.filter(reference__startswith=prefix).order_by('-reference').values_list('reference', flat=True).first()
        number = int(last.rsplit('-', 1)[1]) + 1 if last else 1
        return f'{prefix}{number:04d}'

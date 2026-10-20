from django.db import models

from app.imaging import optimize_field


class PartCategoryMirror(models.Model):
    """Miroir de public.apps.parts.PartCategory (table parts_partcategory,
    connexion 'public_db'). Jamais migré depuis ce projet — le schéma est possédé
    et migré par le projet public."""

    name = models.CharField('Nom', max_length=80)
    icon = models.CharField('Icône', max_length=40, default='settings')
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Visible', default=True)

    class Meta:
        managed = False
        db_table = 'parts_partcategory'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class PartMirror(models.Model):
    """Miroir de public.apps.parts.Part (table parts_part). Créée et modifiée
    ici (saisie ou import CSV) ; le site public ne fait que la lire."""

    class Condition(models.TextChoices):
        NEW = 'neuf', 'Neuf'
        REFURBISHED = 'reconditionne', 'Reconditionné'
        USED = 'occasion', 'Occasion'

    class Availability(models.TextChoices):
        AVAILABLE = 'disponible', 'Disponible'
        UNAVAILABLE = 'indisponible', 'Indisponible'
        TO_CONFIRM = 'a_confirmer', 'À confirmer'

    reference = models.CharField('Référence Djona', max_length=60)
    name = models.CharField('Désignation', max_length=150)
    manufacturer_reference = models.CharField('Référence fabricant (OEM)', max_length=80, blank=True)
    brand = models.CharField('Marque de la pièce', max_length=80, blank=True)
    category = models.ForeignKey(PartCategoryMirror, verbose_name='Catégorie', on_delete=models.PROTECT, related_name='parts')
    condition = models.CharField('État', max_length=20, choices=Condition.choices, blank=True)
    price = models.PositiveIntegerField('Prix (FCFA)', null=True, blank=True)
    availability = models.CharField('Disponibilité', max_length=20, choices=Availability.choices, default=Availability.TO_CONFIRM)
    warranty = models.CharField('Garantie', max_length=150, blank=True)
    lead_time = models.CharField('Délai estimé', max_length=100, blank=True)
    description = models.TextField('Description', blank=True)
    is_featured = models.BooleanField('Pièce populaire', default=False)
    is_active = models.BooleanField('Visible sur le site', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'parts_part'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.reference})'


class PartImageMirror(models.Model):
    part = models.ForeignKey(PartMirror, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='parts/', max_length=255)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'parts_partimage'
        ordering = ['order', 'id']

    def save(self, *args, **kwargs):
        self.image = optimize_field(self.image)
        super().save(*args, **kwargs)


class PartCompatibilityMirror(models.Model):
    part = models.ForeignKey(PartMirror, on_delete=models.CASCADE, related_name='compatibilities')
    make = models.CharField(max_length=60)
    model = models.CharField(max_length=80, blank=True)
    year_from = models.PositiveSmallIntegerField(null=True, blank=True)
    year_to = models.PositiveSmallIntegerField(null=True, blank=True)
    engine = models.CharField(max_length=80, blank=True)

    class Meta:
        managed = False
        db_table = 'parts_partcompatibility'
        ordering = ['make', 'model', 'year_from']


class PartRequestMirror(models.Model):
    """Miroir de public.apps.parts.PartRequest (table parts_partrequest).
    Créées par le formulaire public ; le staff fait avancer le dossier."""

    class Status(models.TextChoices):
        NEW = 'nouvelle', 'Nouvelle demande'
        SEARCHING = 'en_recherche', 'En recherche'
        PROPOSED = 'proposition_envoyee', 'Proposition envoyée'
        ACCEPTED = 'acceptee', 'Acceptée par le client'
        DECLINED = 'refusee', 'Refusée par le client'
        NO_FOLLOW_UP = 'sans_suite', 'Sans suite'

    class RequestType(models.TextChoices):
        SEARCH = 'introuvable', 'Pièce introuvable'
        INTEREST = 'interesse', 'Intéressé par une pièce'

    reference = models.CharField(max_length=20)
    request_type = models.CharField(max_length=20, choices=RequestType.choices, default=RequestType.SEARCH)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    make = models.CharField(max_length=60, blank=True)
    model = models.CharField(max_length=80, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    engine = models.CharField(max_length=80, blank=True)
    part_name = models.CharField(max_length=150)
    part_reference = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='part_requests/', max_length=255, blank=True)
    part = models.ForeignKey(PartMirror, null=True, blank=True, on_delete=models.SET_NULL, related_name='requests')
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEW)
    proposed_price = models.PositiveIntegerField(null=True, blank=True)
    proposed_lead_time = models.CharField(max_length=100, blank=True)
    internal_note = models.TextField(blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'parts_partrequest'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

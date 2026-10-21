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


# ── Panier et commandes de pièces (miroirs de public.apps.parts) ──────────────

class PartsSettingsMirror(models.Model):
    """Miroir de public PartsSettings (table parts_partssettings) — une seule ligne (pk=1)."""

    class CommissionType(models.TextChoices):
        NONE = 'aucune', 'Aucune (non définie)'
        PERCENT = 'pourcentage', 'Pourcentage du sous-total'
        FIXED = 'fixe', 'Montant fixe par commande'

    commission_type = models.CharField('Règle de commission', max_length=15, choices=CommissionType.choices, default='aucune')
    commission_value = models.DecimalField('Valeur', max_digits=10, decimal_places=2, null=True, blank=True)
    payment_terms = models.TextField('Modalités de paiement affichées au client', blank=True)
    pickup_instructions = models.TextField('Lieu et conditions de retrait', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'parts_partssettings'


class DeliveryZoneMirror(models.Model):
    name = models.CharField('Zone', max_length=100)
    fee = models.PositiveIntegerField('Frais de livraison (FCFA)', null=True, blank=True)
    lead_time = models.CharField('Délai estimé', max_length=100, blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Proposée', default=True)

    class Meta:
        managed = False
        db_table = 'parts_deliveryzone'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class PartOrderMirror(models.Model):
    """Miroir de public PartOrder (table parts_partorder). Créée par le site ; le staff la
    fait avancer (statuts contrôlés) et renseigne frais, paiement et commission."""

    class Status(models.TextChoices):
        PENDING = 'en_attente', 'En attente de confirmation'
        CONFIRMED = 'confirmee', 'Confirmée'
        PREPARING = 'en_preparation', 'En préparation'
        READY = 'prete_retrait', 'Prête au retrait'
        SHIPPING = 'en_livraison', 'En livraison'
        DONE = 'livree_retiree', 'Livrée / retirée'
        CANCELLED = 'annulee', 'Annulée'
        FAILED = 'echec', 'Échec de traitement'

    class PaymentStatus(models.TextChoices):
        PENDING = 'en_attente', 'En attente'
        PARTIAL = 'partiel', 'Partiellement payé'
        PAID = 'paye', 'Payé'

    # Mêmes transitions que public PartOrder.TRANSITIONS — à modifier ensemble.
    TRANSITIONS = {
        Status.PENDING: [Status.CONFIRMED, Status.CANCELLED, Status.FAILED],
        Status.CONFIRMED: [Status.PREPARING, Status.CANCELLED],
        Status.PREPARING: [Status.READY, Status.SHIPPING, Status.CANCELLED],
        Status.READY: [Status.DONE, Status.CANCELLED],
        Status.SHIPPING: [Status.DONE, Status.FAILED],
        Status.DONE: [],
        Status.CANCELLED: [],
        Status.FAILED: [Status.PENDING, Status.CANCELLED],
    }

    reference = models.CharField(max_length=20)
    customer_type = models.CharField(max_length=15)
    full_name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    reception = models.CharField(max_length=10)
    delivery_zone_id = models.BigIntegerField(null=True, blank=True)
    zone_name = models.CharField(max_length=100, blank=True)
    delivery_address = models.CharField(max_length=255, blank=True)
    instructions = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    subtotal = models.PositiveBigIntegerField(default=0)
    has_unpriced_items = models.BooleanField(default=False)
    delivery_fee = models.PositiveIntegerField('Frais de livraison (FCFA)', null=True, blank=True)
    commission_amount = models.PositiveBigIntegerField('Commission Djona (FCFA)', null=True, blank=True)
    payment_status = models.CharField('Paiement', max_length=15, choices=PaymentStatus.choices, default='en_attente')
    payment_method = models.CharField('Mode de paiement', max_length=60, blank=True)
    payment_reference = models.CharField('Référence de transaction', max_length=100, blank=True)
    amount_paid = models.PositiveBigIntegerField('Montant payé (FCFA)', default=0)
    internal_note = models.TextField('Note interne', blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'parts_partorder'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    @property
    def is_pickup(self):
        return self.reception == 'retrait'

    @property
    def total(self):
        return self.subtotal + (self.delivery_fee or 0)

    @property
    def balance(self):
        return max(self.total - self.amount_paid, 0)

    @property
    def total_is_final(self):
        return not self.has_unpriced_items and not (self.reception == 'livraison' and self.delivery_fee is None)

    @property
    def customer_label(self):
        return f'{self.full_name} ({self.company_name})' if self.company_name else self.full_name

    def next_statuses(self):
        allowed = list(self.TRANSITIONS.get(self.status, []))
        if self.status == self.Status.PREPARING:
            drop = self.Status.SHIPPING if self.is_pickup else self.Status.READY
            allowed = [s for s in allowed if s != drop]
        return allowed


class PartOrderLineMirror(models.Model):
    order = models.ForeignKey(PartOrderMirror, on_delete=models.CASCADE, related_name='lines')
    part_id = models.BigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=150)
    reference = models.CharField(max_length=80)
    unit_price = models.PositiveIntegerField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'parts_partorderline'
        ordering = ['id']

    @property
    def line_total(self):
        return self.unit_price * self.quantity if self.unit_price is not None else None


class PartOrderEventMirror(models.Model):
    order = models.ForeignKey(PartOrderMirror, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20, blank=True, choices=PartOrderMirror.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'parts_partorderevent'
        ordering = ['created_at', 'id']

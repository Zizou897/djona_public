from django.db import IntegrityError, models, transaction
from django.utils import timezone


class Partner(models.Model):
    """Partenaire affiché dans le bandeau « Ils nous font confiance », géré
    depuis le back-office (admin.moderation... voir admin/core/src/partners/).
    Jamais créé/modifié par une action publique — lecture seule côté public.
    """

    name = models.CharField('nom', max_length=100)
    logo = models.ImageField('logo', upload_to='partners/')
    website_url = models.URLField('site web', blank=True)
    order = models.PositiveIntegerField('ordre', default=0)
    publish = models.BooleanField('actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'partenaire'
        verbose_name_plural = 'partenaires'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class NewsletterSubscriber(models.Model):
    """Inscrit à la newsletter — formulaire dans le footer public. Consultable
    en lecture seule depuis le back-office (voir admin/core/src/partners/, ou
    l'app dédiée si le back-office ajoute la sienne).
    """

    email = models.EmailField('email', unique=True)
    is_active = models.BooleanField('actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'abonné newsletter'
        verbose_name_plural = 'abonnés newsletter'
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class TransportVehicleType(models.Model):
    """Types de véhicules proposables dans le formulaire Transport & Logistique.
    Liste modifiable depuis le back-office selon la flotte réelle des partenaires.
    """

    name = models.CharField('nom', max_length=80, unique=True)
    order = models.PositiveIntegerField('ordre', default=0)
    is_active = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'type de véhicule de transport'
        verbose_name_plural = 'types de véhicules de transport'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class TransportRequest(models.Model):
    """Demande de transport soumise depuis la page publique. Créée uniquement
    par le formulaire public ; le back-office la consulte et fait évoluer son statut.
    """

    class Status(models.TextChoices):
        NEW = 'nouvelle', 'Nouvelle demande'
        IN_PROGRESS = 'en_traitement', 'En traitement'
        DONE = 'traitee', 'Traitée'
        CANCELLED = 'annulee', 'Annulée'

    class RequesterType(models.TextChoices):
        INDIVIDUAL = 'particulier', 'Particulier'
        COMPANY = 'entreprise', 'Entreprise'

    reference = models.CharField('numéro de demande', max_length=20, unique=True, editable=False)
    last_name = models.CharField('nom', max_length=100)
    first_name = models.CharField('prénom', max_length=100)
    phone = models.CharField('téléphone', max_length=30)
    email = models.EmailField('email', blank=True)
    requester_type = models.CharField('type de demandeur', max_length=20, choices=RequesterType.choices, default=RequesterType.INDIVIDUAL)
    company_name = models.CharField("nom de l'entreprise", max_length=150, blank=True)
    vehicle_type = models.ForeignKey(TransportVehicleType, verbose_name='type de véhicule', on_delete=models.PROTECT, related_name='requests')
    quantity = models.CharField('nombre de véhicules', max_length=5)
    loading_date = models.DateField('date de chargement')
    loading_place = models.CharField('lieu de chargement', max_length=200)
    delivery_place = models.CharField('lieu de livraison', max_length=200)
    message = models.TextField('informations complémentaires', blank=True)
    status = models.CharField('statut', max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField('date de la demande', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'demande de transport'
        verbose_name_plural = 'demandes de transport'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
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
        prefix = f'DJ-TR-{timezone.localdate().year}-'
        last = cls.objects.filter(reference__startswith=prefix).order_by('-reference').values_list('reference', flat=True).first()
        number = int(last.rsplit('-', 1)[1]) + 1 if last else 1
        return f'{prefix}{number:04d}'

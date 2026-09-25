from django.db import models


class TransportVehicleTypeMirror(models.Model):
    """Miroir de public.apps.core.TransportVehicleType (table
    core_transportvehicletype, connexion 'public_db'). Jamais migré depuis ce
    projet — le schéma est possédé et migré par le projet public. Le staff
    ajuste ici la liste des types proposés dans le formulaire public.
    """

    name = models.CharField(max_length=80, unique=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'core_transportvehicletype'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class TransportRequestMirror(models.Model):
    """Miroir de public.apps.core.TransportRequest (table core_transportrequest).
    Créées uniquement par le formulaire public ; le staff ne modifie que le statut.
    """

    class Status(models.TextChoices):
        NEW = 'nouvelle', 'Nouvelle demande'
        IN_PROGRESS = 'en_traitement', 'En traitement'
        DONE = 'traitee', 'Traitée'
        CANCELLED = 'annulee', 'Annulée'

    reference = models.CharField(max_length=20, unique=True)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    requester_type = models.CharField(max_length=20)
    company_name = models.CharField(max_length=150, blank=True)
    vehicle_type = models.ForeignKey(TransportVehicleTypeMirror, on_delete=models.PROTECT, related_name='requests')
    quantity = models.CharField(max_length=5)
    loading_date = models.DateField()
    loading_place = models.CharField(max_length=200)
    delivery_place = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'core_transportrequest'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def requester_label(self):
        return 'Entreprise' if self.requester_type == 'entreprise' else 'Particulier'

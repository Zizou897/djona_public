from django.db import models


class ContactMessageMirror(models.Model):
    """Miroir de public.apps.core.ContactMessage (table core_contactmessage,
    connexion 'public_db'). Jamais migré depuis ce projet — le schéma est possédé
    et migré par le projet public. Le staff ne modifie que le statut.
    """

    class Status(models.TextChoices):
        NEW = 'nouveau', 'Nouveau'
        IN_PROGRESS = 'en_traitement', 'En traitement'
        DONE = 'traite', 'Traité'

    SUBJECT_LABELS = {
        'achat': 'Acheter un véhicule',
        'vente': 'Vendre mon véhicule',
        'transport': 'Transport & logistique',
        'partenariat': 'Partenariat',
        'autre': 'Autre',
        'question': 'Question (FAQ)',
    }

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    subject = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'core_contactmessage'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.display_name} — {self.subject_label}'

    @property
    def display_name(self):
        return self.full_name or 'Visiteur'

    @property
    def subject_label(self):
        return self.SUBJECT_LABELS.get(self.subject, self.subject)


class SiteContactMirror(models.Model):
    """Miroir de public.apps.core.SiteContact (table core_sitecontact) : les
    coordonnées affichées sur le site public. Une seule ligne (pk=1), créée par
    la migration publique ; le staff ne fait que la modifier.
    """

    phone = models.CharField('Téléphone', max_length=30)
    whatsapp = models.CharField('Numéro WhatsApp', max_length=30)
    email = models.EmailField('Email')
    address = models.CharField('Siège social', max_length=255)
    city = models.CharField('Ville', max_length=100)
    facebook_url = models.URLField('Facebook', blank=True)
    instagram_url = models.URLField('Instagram', blank=True)
    tiktok_url = models.URLField('TikTok', blank=True)
    linkedin_url = models.URLField('LinkedIn', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'core_sitecontact'

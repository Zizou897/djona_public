from django.conf import settings
from django.db import models

from app.models import Convention


class Annonce(Convention):
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_ATTENTE = 'en_attente', 'En attente'
        PUBLIEE = 'publiee', 'Publiée'
        REFUSEE = 'refusee', 'Refusée'

    class Carburant(models.TextChoices):
        ESSENCE = 'essence', 'Essence'
        DIESEL = 'diesel', 'Diesel'
        HYBRIDE = 'hybride', 'Hybride'
        ELECTRIQUE = 'electrique', 'Électrique'

    class BoiteVitesses(models.TextChoices):
        MANUELLE = 'manuelle', 'Manuelle'
        AUTOMATIQUE = 'automatique', 'Automatique'

    class MotifRefus(models.TextChoices):
        INFOS_INSUFFISANTES = 'infos_insuffisantes', 'Informations insuffisantes'
        MAUVAISES_PHOTOS = 'mauvaises_photos', 'Mauvaises photos'
        VEHICULE_INTERDIT = 'vehicule_interdit', 'Véhicule interdit'
        SUSPICION_FRAUDE = 'suspicion_fraude', 'Suspicion de fraude'

    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='annonces')
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    prix = models.PositiveIntegerField()
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20, choices=Carburant.choices)
    boite_vitesses = models.CharField(max_length=20, choices=BoiteVitesses.choices)
    couleur = models.CharField(max_length=50)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, db_index=True)
    motif_refus = models.CharField(max_length=30, choices=MotifRefus.choices, blank=True)

    class Meta:
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'

    def save(self, *args, **kwargs):
        # Ne se synchronise qu'à .save() — un .update()/.bulk_create() en masse
        # contournerait ceci et laisserait `publish` obsolète. Toujours passer par
        # .save() sur une instance individuelle.
        self.publish = self.statut == self.Statut.PUBLIEE
        super().save(*args, **kwargs)


class AnnoncePhoto(models.Model):
    annonce = models.ForeignKey(Annonce, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='annonces/%Y/%m/')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'annonce_photos'
        ordering = ['ordre']

    def __str__(self):
        return f'Photo #{self.ordre} — {self.annonce}'

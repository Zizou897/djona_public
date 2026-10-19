from django.conf import settings
from django.db import models
from django.utils import formats

from app.imaging import optimize_field
from app.models import Convention, Profil


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

    class Etat(models.TextChoices):
        NEUF = 'neuf', 'Neuf'
        OCCASION = 'occasion', 'Occasion'

    class TypeAnnonce(models.TextChoices):
        VENTE = 'vente', 'À vendre'
        LOCATION = 'location', 'À louer'

    class MotifRefus(models.TextChoices):
        INFOS_INSUFFISANTES = 'infos_insuffisantes', 'Informations insuffisantes'
        MAUVAISES_PHOTOS = 'mauvaises_photos', 'Mauvaises photos'
        VEHICULE_INTERDIT = 'vehicule_interdit', 'Véhicule interdit'
        SUSPICION_FRAUDE = 'suspicion_fraude', 'Suspicion de fraude'

    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='annonces')
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    # Prix de vente ; vaut 0 pour une annonce de location (tarifs ci-dessous).
    prix = models.PositiveIntegerField()
    type_annonce = models.CharField(
        "type d'annonce", max_length=10, choices=TypeAnnonce.choices, default=TypeAnnonce.VENTE, db_index=True,
    )
    # Location : le vendeur renseigne les périodes qu'il propose (au moins une).
    prix_jour = models.PositiveIntegerField('tarif par jour (FCFA)', null=True, blank=True)
    prix_semaine = models.PositiveIntegerField('tarif par semaine (FCFA)', null=True, blank=True)
    prix_mois = models.PositiveIntegerField('tarif par mois (FCFA)', null=True, blank=True)
    caution = models.PositiveIntegerField('caution (FCFA)', null=True, blank=True)
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20, choices=Carburant.choices)
    boite_vitesses = models.CharField(max_length=20, choices=BoiteVitesses.choices)
    couleur = models.CharField(max_length=50)
    # blank=True pour les annonces créées avant l'ajout de ces champs ; le
    # formulaire les rend obligatoires pour toute nouvelle saisie.
    etat = models.CharField('état', max_length=20, choices=Etat.choices, blank=True)
    ville = models.CharField('ville du véhicule', max_length=30, choices=Profil.Ville.choices, blank=True)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, db_index=True)
    motif_refus = models.CharField(max_length=30, choices=MotifRefus.choices, blank=True)

    class Meta:
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'

    @property
    def est_location(self):
        return self.type_annonce == self.TypeAnnonce.LOCATION

    @property
    def tarifs_location(self):
        """[(période, montant)] des périodes renseignées, de la plus courte à la plus longue."""
        return [(periode, montant) for periode, montant in (
            ('jour', self.prix_jour), ('semaine', self.prix_semaine), ('mois', self.prix_mois),
        ) if montant]

    @property
    def resume_prix(self):
        """Texte de prix pour les listes : « 8 500 000 FCFA » ou « 25 000 FCFA / jour »."""
        if self.est_location:
            tarifs = self.tarifs_location
            if not tarifs:
                return 'Tarif non renseigné'
            periode, montant = tarifs[0]
            return f'{formats.number_format(montant, force_grouping=True)} FCFA / {periode}'
        return f'{formats.number_format(self.prix, force_grouping=True)} FCFA'

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

    def save(self, *args, **kwargs):
        # Toute photo téléversée est stockée en WebP (largeur plafonnée) : le
        # catalogue public ne sert jamais l'image brute d'un téléphone (3-8 Mo).
        self.image = optimize_field(self.image)
        super().save(*args, **kwargs)

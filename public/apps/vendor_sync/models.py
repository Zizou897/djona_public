from django.db import models


class VendeurMirror(models.Model):
    """Miroir en lecture seule de vendor.app.Utilisateur (schéma djona_vendor,
    connexion 'vendor_db'). Jamais migré depuis ce projet — le schéma réel est
    possédé et migré par le projet vendor. Ne jamais écrire dedans.
    """

    email = models.EmailField()
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10)
    type_compte = models.CharField(max_length=20)
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'vendeur_utilisateurs'

    def __str__(self):
        return f'{self.prenom} {self.nom} ({self.email})'


class ProfilMirror(models.Model):
    """Miroir en lecture seule de vendor.app.Profil (table app_profil, schéma
    djona_vendor). Jamais migré depuis ce projet.
    """

    user = models.OneToOneField(
        VendeurMirror, on_delete=models.DO_NOTHING, related_name='profil', db_constraint=False,
    )
    ville = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    raison_sociale = models.CharField(max_length=150, blank=True)

    class Meta:
        managed = False
        db_table = 'app_profil'


class AnnonceMirror(models.Model):
    """Miroir en lecture seule de vendor.annonces.Annonce (schéma djona_vendor,
    connexion 'vendor_db'). Jamais migré depuis ce projet.

    Usage : LIRE les annonces dont `statut == 'publiee'` (validées par l'admin,
    voir admin/moderation/models.py::AnnonceMirror) pour les faire apparaître
    sur le catalogue public via apps.vendor_sync.management.commands.sync_validated_annonces.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_ATTENTE = 'en_attente', 'En attente'
        PUBLIEE = 'publiee', 'Publiée'
        REFUSEE = 'refusee', 'Refusée'

    vendeur = models.ForeignKey(
        VendeurMirror, on_delete=models.DO_NOTHING, related_name='annonces', db_constraint=False,
    )
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    prix = models.PositiveIntegerField()
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20)
    boite_vitesses = models.CharField(max_length=20)
    couleur = models.CharField(max_length=50)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'


class AnnoncePhotoMirror(models.Model):
    annonce = models.ForeignKey(
        AnnonceMirror, on_delete=models.DO_NOTHING, related_name='photos', db_constraint=False,
    )
    image = models.ImageField(upload_to='annonces/%Y/%m/')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'annonce_photos'
        ordering = ['ordre']

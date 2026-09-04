from django.db import models


class CompteVendeur(models.Model):
    """Miroir en lecture/écriture de vendor.app.Utilisateur (schéma djona_vendor,
    connexion 'vendor_db'). Ce modèle n'est jamais migré depuis ce projet — le
    schéma réel est possédé et migré par le projet vendor.

    Usage prévu : LIRE les informations de compte, et METTRE À JOUR les seuls champs
    de modération (`statut_compte`, `is_active`). Ce modèle ne doit jamais servir à
    CRÉER un compte, ni à écrire dans `password` : la création de compte est
    exclusivement gérée par le flux d'inscription du projet vendor, via
    `UtilisateurManager.create_user`, qui normalise l'email et hache le mot de passe.
    Un `.create()`/`.save()` fait depuis ce mirror écrirait un mot de passe en clair
    et contournerait ce hachage — ne pas s'en servir pour fabriquer des comptes.

    À ne pas confondre avec `annonces.Vendeur` : ce dernier est un simple
    sous-document non authentifié attaché à une annonce (table `vendeurs`, concept
    différent malgré le même mot « vendeur ») ; il sera retiré lors d'un plan
    ultérieur au moment où l'ancienne app `annonces` sera dépréciée. `CompteVendeur`
    ici représente le vrai compte authentifié côté vendor.
    """

    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    class StatutCompte(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'

    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10)
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices, default=TypeCompte.PARTICULIER)
    statut_compte = models.CharField(max_length=20, choices=StatutCompte.choices, default=StatutCompte.EN_ATTENTE)
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()
    last_login = models.DateTimeField(null=True, blank=True)
    password = models.CharField(max_length=128)
    # is_staff/is_superuser (colonnes réelles de PermissionsMixin, héritées côté vendor)
    # ne sont jamais utilisées côté admin, mais sont NOT NULL sans défaut au niveau de
    # la base — nécessaires ici pour que `.create()`/`.save()` fonctionnent sans erreur
    # de colonne manquante, comme `password` ci-dessus.
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'vendeur_utilisateurs'

    def __str__(self):
        return f'{self.prenom} {self.nom} ({self.email})'


class AnnonceMirror(models.Model):
    """Miroir en lecture/écriture de vendor.annonces.Annonce (schéma djona_vendor,
    connexion 'vendor_db'). Jamais migré depuis ce projet.

    Usage prévu : LIRE les annonces, et METTRE À JOUR les seuls champs de
    modération (`statut`) sur des annonces existantes. Ce modèle ne doit jamais
    servir à CRÉER une annonce : la création est exclusivement gérée par le flux
    de publication du projet vendor.
    """

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

    vendeur = models.ForeignKey(
        CompteVendeur, on_delete=models.DO_NOTHING, related_name='annonces', db_constraint=False,
    )
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    prix = models.PositiveIntegerField()
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20, choices=Carburant.choices)
    boite_vitesses = models.CharField(max_length=20, choices=BoiteVitesses.choices)
    couleur = models.CharField(max_length=50)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices)
    motif_refus = models.CharField(max_length=30, choices=MotifRefus.choices, blank=True)
    created_at = models.DateTimeField()
    # update_at/publish (colonnes réelles héritées de app.Convention côté vendor) ne
    # sont jamais lues/écrites intentionnellement depuis ce mirror, mais sont NOT NULL
    # sans défaut au niveau de la base — nécessaires ici pour que `.create()`/`.save()`
    # fonctionnent sans erreur de colonne manquante, comme pour CompteVendeur ci-dessus.
    update_at = models.DateTimeField()
    publish = models.BooleanField(default=False)

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


class VehicleMirror(models.Model):
    """Miroir en lecture/écriture de public.apps.catalog.Vehicle (schéma
    djona_public, connexion 'public_db'). Jamais migré depuis ce projet.

    Usage prévu : LIRE le véhicule correspondant à une annonce déjà
    synchronisée (via `source_annonce_id`), et METTRE À JOUR le seul champ
    `publish` — pour activer/désactiver son affichage sur le marketplace
    indépendamment du statut de modération côté vendor. Ne doit jamais servir
    à créer/supprimer un véhicule : ce cycle de vie est possédé par
    apps.vendor_sync.sync_validated_annonces côté projet public.
    """

    source_annonce_id = models.PositiveIntegerField(unique=True, null=True)
    brand = models.CharField(max_length=80)
    model_name = models.CharField(max_length=120)
    publish = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'catalog_vehicle'

    def __str__(self):
        return f'{self.brand} {self.model_name}'

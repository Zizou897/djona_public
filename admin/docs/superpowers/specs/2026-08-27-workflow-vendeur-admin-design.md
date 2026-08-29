# Workflow vendeur ↔ admin (activation de compte + gestion et validation d'annonces) — Design

## Contexte

Djona a deux backoffices Django indépendants, connectés au même serveur MySQL local
(`127.0.0.1:3307`) mais avec des schémas séparés :

- **`vendor/core`** (schéma `djona_vendor`) — portail vendeur. Inscription/connexion
  fonctionnelles. Modèle `app.Utilisateur` (`AUTH_USER_MODEL`, email + mot de passe,
  `nom`/`prenom`/`telephone`/`type_compte` particulier|professionnel). Dashboard actuel :
  page de bienvenue statique, aucune gestion d'annonces.
- **`admin/core`** (schéma `djona_admin`) — portail admin. Connexion/dashboard
  fonctionnels. App `annonces` avec modèles `Vendeur` (fiche minimale sans compte,
  créée par l'admin), `Annonce`, `AnnoncePhoto`, et un wizard 4 étapes
  (`AnnonceCreateView`) où l'admin crée une annonce pour un vendeur.

## Objectif

1. Un vendeur s'inscrit et se connecte en choisissant son type de compte (déjà en place).
2. Le dashboard admin liste tout vendeur venant de s'inscrire et peut activer son compte.
3. Une fois son compte activé, le vendeur gère ses propres annonces et décide de les
   soumettre à publication.
4. Quand le vendeur soumet une annonce, le dashboard admin la valide (ou la refuse).

## Décisions validées

- **Activation du compte** : ne bloque pas la connexion. Un vendeur `en_attente` peut se
  connecter et voir un dashboard limité, mais ne peut pas gérer d'annonces tant que
  l'admin n'a pas activé son compte. `is_active` (Django) reste `True` par défaut et gère
  uniquement la capacité de connexion ; `statut_compte` (nouveau champ) gère l'accès aux
  fonctionnalités métier.
- **Propriété de la création d'annonce** : le vendeur crée désormais ses propres annonces
  depuis son compte. Le wizard admin existant (`AnnonceCreateView`, création pour un
  vendeur sans compte) est retiré. Le modèle `Vendeur` (sans authentification) est retiré
  — `Annonce.vendeur` pointe directement sur `Utilisateur`.
- **Partage de données entre projets** : routeur multi-base Django (option A, retenue
  parmi 3 approches présentées : multi-base / API interne / synchronisation périodique).
  Les données vendeur + annonces vivent dans `djona_vendor` (propriétaire : projet
  vendor). Le projet admin obtient une deuxième connexion base de données
  (`DATABASES['vendor_db']`) et des modèles miroirs `managed=False` pour lire/écrire
  directement sur les mêmes tables, sans délai de synchronisation et sans risque de
  collision de migrations (les modèles `managed=False` ne sont jamais touchés par
  `migrate`).

## Modèle de données

### `vendor/core/src/app/models.py` — `Utilisateur` (modifié)

Ajout d'un champ de statut de compte, distinct de `is_active` :

```python
class Utilisateur(AbstractBaseUser, PermissionsMixin):
    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    class StatutCompte(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'

    # ... champs existants (email, nom, prenom, telephone, type_compte, is_active,
    # is_staff, date_joined) inchangés ...

    statut_compte = models.CharField(
        max_length=20, choices=StatutCompte.choices, default=StatutCompte.EN_ATTENTE,
    )
```

Tout nouveau compte démarre à `en_attente`. Seul l'admin (via l'app `moderation`) le fait
passer à `actif` ou `suspendu`.

### `vendor/core/src/annonces/models.py` (nouvelle app, côté vendor)

Reprend la structure déjà validée côté admin, avec le FK `vendeur` repointé sur
`settings.AUTH_USER_MODEL` :

```python
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

    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='annonces',
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
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON)

    class Meta:
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'

    def save(self, *args, **kwargs):
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
```

`on_delete=CASCADE` (plutôt que `PROTECT` comme dans l'ancien modèle) : une annonce
appartient désormais à un compte utilisateur réel du même projet, la suppression d'un
compte doit pouvoir emporter ses annonces sans blocage manuel — cohérent avec le fait que
c'est maintenant une relation propriétaire/possession, pas une référence à un tiers
externe.

`Convention` (abstrait, `created_at`/`update_at`/`publish`) est dupliqué depuis
`vendor/core/src/app/models.py`, qui l'a déjà (copié du même squelette `django-init`).

### `admin/core/src/moderation/models.py` (nouvelle app, côté admin)

Modèles miroirs, en lecture/écriture directe sur les tables du schéma `djona_vendor` via
la connexion `vendor_db`. Champs identiques aux modèles réels, `managed = False` :

```python
from django.db import models


class CompteVendeur(models.Model):
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
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices)
    statut_compte = models.CharField(max_length=20, choices=StatutCompte.choices)
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'vendeur_utilisateurs'

    def __str__(self):
        return f'{self.prenom} {self.nom} ({self.email})'


class AnnonceMirror(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_ATTENTE = 'en_attente', 'En attente'
        PUBLIEE = 'publiee', 'Publiée'
        REFUSEE = 'refusee', 'Refusée'

    vendeur = models.ForeignKey(
        CompteVendeur, on_delete=models.DO_NOTHING, related_name='annonces', db_constraint=False,
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
```

`db_constraint=False` sur les FK miroirs : Django ne doit pas tenter de créer/valider une
contrainte de clé étrangère au niveau MySQL depuis une connexion qui ne gère pas ce
schéma. `on_delete=DO_NOTHING` : la suppression réelle est gérée côté vendor (propriétaire
des données), le miroir ne fait qu'observer.

Toutes les requêtes ORM sur ces trois modèles passent explicitement par
`.using('vendor_db')` (pas de `DATABASE_ROUTERS` global — le besoin est limité à
quelques vues, l'explicite est plus simple à suivre que le routage automatique).

## Configuration base de données (admin)

`admin/core/src/core/settings.py` — deuxième alias de connexion, même serveur/utilisateur
MySQL que `default`, seul le nom de la base change :

```python
DATABASES = {
    'default': { ... },  # inchangé
    'vendor_db': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('VENDOR_MYSQL_DB', default='djona_vendor'),
        'USER': config('MYSQL_USER', default='djona_app'),
        'PASSWORD': config('MYSQL_PASSWORD', default=''),
        'HOST': config('MYSQL_HOST', default='127.0.0.1'),
        'PORT': config('MYSQL_PORT', default='3307'),
        'OPTIONS': {'ssl': {'ssl-mode': 'REQUIRED'}},
    } if config('USE_MYSQL', default=False, cast=bool) else {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR.parent / 'vendor_mirror.sqlite3',
    },
}
```

`admin/core/.env` — nouvelle variable `VENDOR_MYSQL_DB=djona_vendor` (réutilise
`MYSQL_USER`/`MYSQL_PASSWORD`/`MYSQL_HOST`/`MYSQL_PORT` déjà présents).

## Workflow vendeur (`vendor/core`)

### Dashboard (`TableauDeBordVendeurView`, modifié)

Rendu conditionné par `request.user.statut_compte` :

- `en_attente` → message « Votre compte est en cours de validation par notre équipe. »,
  pas d'accès aux annonces.
- `suspendu` → message « Compte suspendu, contactez le support. », même restriction.
- `actif` → dashboard réel : compteurs par statut d'annonce + lien vers « Mes annonces ».

### App `annonces` (nouvelle)

Toutes les vues de cette section filtrent systématiquement sur
`Annonce.objects.filter(vendeur=request.user)` avant toute lecture ou action — un
vendeur ne voit et ne peut agir que sur ses propres annonces. Une tentative d'accès à
l'annonce d'un autre vendeur (URL devinée/modifiée) renvoie 404 (queryset scopé, pas de
vérification a posteriori).

- **Liste** (`MesAnnoncesListView`) : annonces du vendeur connecté, triées par date,
  badge de statut. Accès protégé par `statut_compte == actif` en plus de
  `LoginRequiredMixin` (sinon redirection vers le dashboard avec message).
- **Création** (`AnnonceCreateView`, wizard 4 étapes réutilisant la structure déjà conçue
  côté admin — infos véhicule, caractéristiques, description, photos) : sauvegarde en
  `brouillon`, `vendeur = request.user` (forcé côté serveur, jamais depuis les données du
  formulaire).
- **Édition** (`AnnonceUpdateView`, queryset scopé au vendeur connecté) : autorisée
  seulement si `statut in (brouillon, refusee)`. Une annonce `refusee` éditée repasse en
  `brouillon`. `en_attente`/`publiee` → lecture seule (redirection avec message si
  tentative d'édition).
- **Publier** (`AnnoncePublierView`, POST uniquement, queryset scopé au vendeur
  connecté) : `brouillon` → `en_attente`. Ignore silencieusement (redirection + message)
  toute tentative sur un autre statut.

## Workflow admin (`admin/core`)

### App `moderation` (nouvelle)

- **Liste des vendeurs** (`VendeurListView`, `/vendeurs/`) : tous les `CompteVendeur`
  (`.using('vendor_db')`), triés `en_attente` en premier. Colonnes : nom, email,
  téléphone, type, date d'inscription, statut.
- **Activer / Suspendre** (`ActiverVendeurView`, `SuspendreVendeurView`, POST
  uniquement) : changent `statut_compte` sur `vendor_db`.
- **File de validation** (`AnnonceModerationListView`, `/annonces-a-valider/`) :
  `AnnonceMirror` filtrées `statut='en_attente'` (`.using('vendor_db')`), avec vendeur et
  résumé véhicule.
- **Détail annonce** (`AnnonceModerationDetailView`) : toutes les infos + photos
  (`AnnoncePhotoMirror`).
- **Publier / Refuser** (`PublierAnnonceView`, `RefuserAnnonceView`, POST uniquement) :
  changent `statut` sur `vendor_db`.

### Retiré

- App `annonces` côté admin (modèles `Vendeur`/`Annonce`/`AnnoncePhoto`, migrations,
  `AnnonceCreateView`, templates du wizard, `templates/annonces/`).
- Lien sidebar « Nouvelle annonce » → remplacé par « Vendeurs » et « Annonces à valider ».

## Hors scope (confirmé avec l'utilisateur)

- Pas de motif de refus obligatoire — juste un changement de statut. Ajoutable plus tard.
- Pas de notification email/SMS au vendeur lors de l'activation ou de la
  validation/refus — le vendeur voit le changement d'état à sa prochaine connexion.

## Tests

- `vendor/core` : modèle `Utilisateur.statut_compte` (défaut `en_attente`), dashboard
  selon statut, CRUD `Annonce` (création, édition selon statut, action publier),
  permissions (annonce d'un autre vendeur invisible/non modifiable).
- `admin/core` : liste vendeurs (via `vendor_db`), actions activer/suspendre, liste
  annonces à valider, actions publier/refuser, vérification que ces vues échouent
  proprement si `vendor_db` est indisponible.
- Test d'intégration bout en bout (les deux projets, même base MySQL locale) : un vendeur
  s'inscrit → invisible en `actif` → admin l'active → vendeur crée et publie une annonce
  → admin la voit en attente → admin valide → statut `publiee` cohérent des deux côtés.

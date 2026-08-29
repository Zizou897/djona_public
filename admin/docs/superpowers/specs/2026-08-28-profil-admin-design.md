# Page "Gestion du Profil" — backoffice admin — Design

## Contexte

Le projet `admin/core` (Django) a déjà une connexion staff fonctionnelle
(`AdminLoginView` → `/connexion/`, backend `EmailOrUsernameBackend`) et un dashboard
staff (`AdminDashboardView` → `/tableau-de-bord/`, `LoginRequiredMixin` +
`UserPassesTestMixin(is_staff)`), adapté de la maquette `_back_office/desktop/admin_dashboard_djona`.

La maquette `admin/_utilisateur/desktop/param_tres_du_profil_djona` montre un écran
"Gestion du Profil" pensé pour un compte acheteur (toggle Particulier/Professionnel,
compteur "Annonces actives", sidebar Mes Annonces/Mes Favoris/Demandes Djona, topbar
publique Djona). Le projet `admin` n'a aujourd'hui qu'un seul système de compte : le
`django.contrib.auth.User` staff. Il n'existe pas de compte acheteur séparé.

## Objectif

Donner à l'utilisateur staff connecté une page `/profil/` pour consulter et modifier ses
informations personnelles, sa sécurité (mot de passe, préférence 2FA) et ses préférences
de notification/langue — en réutilisant l'auth et le shell (topbar + sidebar) déjà en
place pour le dashboard admin, pas ceux de la maquette.

## Décisions validées

- **Compte concerné** : le compte staff déjà connecté (`request.user`, `is_staff`), pas un
  nouveau système de compte acheteur — ce dernier serait un chantier séparé bien plus
  large (auth dédiée, modèle de compte, écrans de connexion/inscription acheteur).
- **Shell (topbar + sidebar)** : celui déjà en place dans `dashboard_admin.html`
  (Dashboard / Annonces à valider / Vendeurs / Transactions / Settings / Déconnexion),
  pas la nav publique Djona ni la sidebar acheteur de la maquette. Extrait dans un include
  partagé pour éviter la duplication (voir "Refactor shell" ci-dessous) — ce point était
  déjà noté comme dette dans `analyse_et_taches_djona.md` ("factoriser sidebar/topbar en
  includes").
- **Type de compte / Annonces actives** : ces deux éléments de la maquette n'ont pas de
  sens pour un compte staff. Remplacés par : rôle (Super Administrateur si
  `is_superuser`, sinon Administrateur — même logique que la topbar du dashboard) et date
  d'inscription (`user.date_joined`).
- **2FA** : préférence stockée uniquement (`Profil.two_factor_enabled`, booléen). Pas de
  vérification OTP/SMS réelle — ce toggle prépare un futur chantier 2FA, il ne l'implémente
  pas.
- **Mot de passe** : vrai formulaire Django (`PasswordChangeForm`), révélé sous le bouton
  "Modifier le mot de passe" (affichage/masquage en JS vanilla, pas de librairie modale),
  soumis vers une vue dédiée. `update_session_auth_hash` pour ne pas déconnecter
  l'utilisateur après changement.
- **Avatar** : upload réel (`ImageField`), servi depuis `MEDIA_URL`. Avatar par défaut
  (icône `person`) si aucune image.
- **Langue** : préférence stockée (`Profil.langue`, choix fr/en) sans effet i18n réel — le
  projet n'a aujourd'hui aucune traduction (`LANGUAGE_CODE` figé à `fr-fr`, pas de
  fichiers `.po`). Mettre en place l'i18n complet est hors périmètre.
- **Badges décoratifs de la maquette** :
  - "Compte vérifié" → affiché si `user.is_active`.
  - Barre "Sécurité du compte" → 50 % si `two_factor_enabled=False`, 100 % si `True`.
  - Coche "email vérifié" → retirée (aucun système de vérification d'email dans le
    projet).
  - Badge "WhatsApp Activé" à côté du téléphone → retiré (aucune donnée réelle derrière).

## Modèle de données

Nouveau modèle dans `admin/core/src/app/models.py`, en relation 1-1 avec `User` (créé à
la volée via `get_or_create`, pas de migration de données nécessaire) :

```python
from django.conf import settings
from django.db import models


class Profil(models.Model):
    class Ville(models.TextChoices):
        ABIDJAN_COCODY = 'abidjan_cocody', 'Abidjan, Cocody'
        ABIDJAN_MARCORY = 'abidjan_marcory', 'Abidjan, Marcory'
        ABIDJAN_KOUMASSI = 'abidjan_koumassi', 'Abidjan, Koumassi'
        YAMOUSSOUKRO = 'yamoussoukro', 'Yamoussoukro'
        BOUAKE = 'bouake', 'Bouaké'

    class Langue(models.TextChoices):
        FRANCAIS = 'fr', 'Français'
        ANGLAIS = 'en', 'English'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profil',
    )
    telephone = models.CharField(max_length=30, blank=True)
    ville = models.CharField(max_length=30, choices=Ville.choices, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False)
    langue = models.CharField(max_length=2, choices=Langue.choices, default=Langue.FRANCAIS)
    notif_email = models.BooleanField(default=True)
    notif_whatsapp = models.BooleanField(default=True)
```

Le nom complet (`first_name`/`last_name`), l'email et la date d'inscription restent sur
`User` — pas de duplication.

## Vues & URLs

Dans `admin/core/src/app/views.py` :

- `ProfilView` (`LoginRequiredMixin` + `UserPassesTestMixin(is_staff)`, même garde que
  `AdminDashboardView`) :
  - `GET` : `get_or_create(user=request.user)` puis affiche le formulaire pré-rempli.
  - `POST` : valide et sauvegarde `first_name`/`last_name` (un seul champ "Nom complet" en
    entrée, split sur le premier espace), `email`, `telephone`, `ville`, `avatar`,
    `two_factor_enabled`, `langue`, `notif_email`, `notif_whatsapp`. Message de succès via
    `django.contrib.messages`, redirect vers `/profil/`.
- `ProfilPasswordChangeView` (mêmes gardes, `POST` uniquement) : `PasswordChangeForm`,
  `update_session_auth_hash`, message de succès/erreur, redirect vers `/profil/`.

Dans `admin/core/src/app/urls.py` :

```python
path('profil/', views.ProfilView.as_view(), name='profil_admin'),
path('profil/mot-de-passe/', views.ProfilPasswordChangeView.as_view(), name='profil_mot_de_passe'),
```

Le lien "Settings" de la sidebar (actuellement `{% url 'admin:index' %}`, vers Jazzmin)
pointe désormais vers `{% url 'profil_admin' %}`.

## Formulaires

Dans un nouveau `admin/core/src/app/forms.py` :

- `ProfilForm` (`forms.ModelForm` sur `Profil`, champs `telephone`, `ville`, `avatar`,
  `two_factor_enabled`, `langue`, `notif_email`, `notif_whatsapp`) + champs libres
  `nom_complet` et `email` gérés dans la vue (ou un `forms.Form` composite) pour rester
  simple — un seul formulaire, un seul bouton "Sauvegarder les modifications".
- Changement de mot de passe : `django.contrib.auth.forms.PasswordChangeForm` directement
  (pas besoin de sous-classer, les validators sont déjà configurés dans `settings.py`).

## Template & réutilisation du shell

### Refactor shell (sidebar + nav basse mobile)

Extrait de `dashboard_admin.html` vers `templates/app/includes/sidebar_admin.html`,
paramétré par une variable de contexte `active_nav` (`'dashboard'` ou `'profil'`) pour
appliquer les classes actives au bon lien. `dashboard_admin.html` est mis à jour pour
utiliser cet include (`{% include 'app/includes/sidebar_admin.html' with active_nav='dashboard' %}`)
sans changement de rendu.

La topbar desktop (recherche + notifications + bloc utilisateur) reste dupliquée telle
quelle pour l'instant — son contenu ne change pas d'une page à l'autre, extraire un
second include serait un refactor non lié à ce chantier.

### `templates/app/layout/profil_admin.html`

`{% extends 'app/base/base.html' %}`, structure copiée de la maquette (grid 12 colonnes :
carte profil + widget sécurité en 4 colonnes, formulaire en 8 colonnes) avec :

- Carte profil : avatar (upload via input file caché + bouton caméra, preview JS), nom
  complet, "Membre depuis {{ user.date_joined|date:"F Y" }}", rôle, badge "Compte
  vérifié" conditionnel.
- Widget "Sécurité du compte" : barre de progression 50/100 % calculée en contexte.
- Section "Informations Personnelles" : nom complet, email, téléphone, ville — pas de
  toggle Particulier/Professionnel.
- Section "Sécurité" : bouton "Modifier le mot de passe" (révèle le formulaire
  old/new/confirm en JS), toggle 2FA.
- Section "Préférences & Notifications" : langue (fr/en, décoratif), cases email/WhatsApp.
- Barre d'actions bas de page : "Annuler" (lien vers `/profil/`, reset des champs) et
  "Sauvegarder les modifications" (submit).

Les onglets internes "Informations Générales / Sécurité / Notifications" de la maquette
sont conservés comme ancres visuelles de scroll (pas de logique JS de tabs à réimplémenter
pour ce chantier — tout tient déjà sur une seule page scrollable, comme dans
`dashboard_admin.html`).

## Tests

Dans `admin/core/src/app/tests.py` (ou un fichier dédié `app/tests_profil.py`) :

- `ProfilView` : accès refusé si non connecté / non staff ; `GET` crée le `Profil` s'il
  n'existe pas ; `POST` valide met à jour `User` et `Profil` ; `POST` avec email invalide
  ré-affiche le formulaire avec erreur.
- Upload avatar : `POST` avec fichier image valide stocke le fichier sous `avatars/`.
- `ProfilPasswordChangeView` : ancien mot de passe incorrect → erreur, pas de changement ;
  mot de passe valide → changé, session conservée (`update_session_auth_hash`).

## Hors périmètre (explicitement)

- Système de compte acheteur séparé du compte staff.
- Vérification 2FA réelle (OTP/SMS).
- i18n réel (traduction effective de l'UI en anglais).
- Vérification d'email réelle.
- Intégration WhatsApp réelle.

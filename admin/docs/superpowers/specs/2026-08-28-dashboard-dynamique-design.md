# Tableau de bord admin dynamique + habillage vendeurs/annonces — Design

## Contexte

Le dashboard admin (`/tableau-de-bord/`, `AdminDashboardView` → `dashboard_admin.html`)
affiche aujourd'hui des chiffres et listes 100 % statiques ("1,284" annonces, 3 lignes de
validation en dur, 4 entrées d'activité récente en dur), en attendant que les modèles
métier existent — commentaire explicite dans le template : *"Chiffres de démo en attendant
les modèles Annonce/Utilisateur/Transaction"*.

Ces modèles existent partiellement aujourd'hui, côté `moderation` app (miroirs
lecture/écriture vers le schéma `djona_vendor`, connexion `vendor_db`) :

- `CompteVendeur` (miroir de `vendor.app.Utilisateur`) — comptes vendeur réels, avec
  `type_compte` (particulier/professionnel), `statut_compte`, `date_joined`.
- `AnnonceMirror` (miroir de `vendor.annonces.Annonce`) — annonces réelles, avec `statut`
  (brouillon/en_attente/publiee/refusee), `created_at`, `vendeur` (FK vers
  `CompteVendeur`).

Il n'existe en revanche **aucun modèle Transaction/Séquestre**, ni **aucun journal
d'activité/notification** dans le projet.

Par ailleurs, `VendeurListView` (`/vendeurs/`) et `AnnonceModerationListView`
(`/annonces-a-valider/`) existent déjà et affichent déjà de vraies données (via ces mêmes
modèles miroir), mais avec un habillage visuel différent et plus basique que
`dashboard_admin.html`/`profil_admin.html` : pas de sidebar/topbar partagée, une config
Tailwind dupliquée (sous-ensemble plus ancien/réduit des tokens), juste un `lg:pl-72` sans
sidebar réelle en dessous.

## Objectif

1. Brancher le dashboard sur les vraies données disponibles (annonces, comptes vendeur),
   sans inventer de données pour ce qui n'a pas encore de modèle (transactions).
2. Aligner visuellement `vendeur_liste.html` et `annonce_liste.html` sur le même habillage
   (sidebar, topbar, nav mobile, styles) que le reste du portail admin.

## Décisions validées

- **KPIs avec données réelles** : "Total Annonces" (compte `AnnonceMirror` par statut :
  publiée vs en attente) et "Communauté" (compte `CompteVendeur` par `type_compte` :
  particulier vs professionnel — remplace "vendeurs/acheteurs" du mockup, qui ne
  correspond à aucune donnée réelle : il n'existe pas de compte "acheteur" dans le
  projet).
- **KPIs sans données réelles** : "Séquestre en cours", "Revenu (semaine)" et le bloc
  "Taux de conversion" (bas de la colonne droite) dépendent tous d'un modèle
  Transaction inexistant. Gardent leur emplacement et leur forme visuelle, mais affichent
  un état "Bientôt disponible" au lieu de chiffres inventés — pas de valeur numérique
  statique laissée en place.
- **Validation en attente** : les 5 `AnnonceMirror` les plus récentes avec
  `statut='en_attente'`, triées par `created_at` décroissant, avec vendeur/véhicule/
  prix/date réels. Boutons Valider/Refuser branchés sur les vues d'action existantes
  (`annonce_valider`, `annonce_refuser` — formulaires `POST`, comportement inchangé),
  bouton "Voir le détail" vers `annonce_moderation_detail`. "Voir toutes les annonces en
  attente" pointe vers `annonce_moderation_liste`. Le bouton "Filtrer" reste décoratif
  (hors périmètre de ce chantier).
- **Activité récente** : pas de modèle de journal d'activité dédié — flux composé en
  mémoire à partir de deux sources réelles existantes : inscriptions vendeur
  (`CompteVendeur.date_joined`) et annonces soumises (`AnnonceMirror.created_at`),
  fusionnées et triées par date décroissante, limitées aux 6 événements les plus
  récents. Pas d'entrée "transaction démarrée" ni "utilisateur vérifié" (aucun modèle
  correspondant côté admin aujourd'hui).
- **Habillage vendeurs/annonces** : `vendeur_liste.html` et `annonce_liste.html` adoptent
  `{% include 'app/includes/styles_admin.html' %}`, `{% include 'app/includes/
  sidebar_admin.html' with active_nav=... %}` et `{% include 'app/includes/
  nav_mobile_admin.html' with active_nav=... %}` (mêmes includes que
  `dashboard_admin.html`/`profil_admin.html`), avec un mobile header cohérent avec les
  autres pages. Tableau/cartes redessinés dans le même système visuel (cartes
  `bg-surface-container-lowest` + `shadow-[0_4px_12px_rgba(26,82,118,0.08)]`, badges de
  statut existants conservés). Aucune vue ni logique métier ne change — uniquement le
  template.
- **Nouvel `active_nav`** : les includes partagés supportent déjà `active_nav='dashboard'`
  et `active_nav='profil'`. On ajoute deux valeurs : `'vendeurs'` (pour `vendeur_liste.html`,
  lien "Vendeurs" dans la sidebar) et `'annonces'` (pour `annonce_liste.html`, lien
  "Annonces à valider").

## Requêtes de données

Toutes via `vendor_db` (lecture seule sauf actions déjà existantes) :

```python
# Compteurs KPI
AnnonceMirror.objects.using('vendor_db').filter(statut=AnnonceMirror.Statut.PUBLIEE).count()
AnnonceMirror.objects.using('vendor_db').filter(statut=AnnonceMirror.Statut.EN_ATTENTE).count()
CompteVendeur.objects.using('vendor_db').filter(type_compte=CompteVendeur.TypeCompte.PARTICULIER).count()
CompteVendeur.objects.using('vendor_db').filter(type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL).count()

# Validation en attente (5 dernières)
AnnonceMirror.objects.using('vendor_db').filter(statut=AnnonceMirror.Statut.EN_ATTENTE) \
    .select_related('vendeur').order_by('-created_at')[:5]

# Activité récente (6 dernières, fusion en mémoire — deux querysets distincts, pas de
# jointure SQL possible entre les deux car types d'événements différents)
vendeurs_recents = CompteVendeur.objects.using('vendor_db').order_by('-date_joined')[:6]
annonces_recentes = AnnonceMirror.objects.using('vendor_db').select_related('vendeur') \
    .order_by('-created_at')[:6]
# fusion Python : liste de dicts {type, titre, description, date}, triée par date, tronquée à 6
```

## Vue

`AdminDashboardView` (dans `admin/core/src/app/views.py`) passe de `TemplateView` simple
(hérite `StaffRequisMixin`) à une vue avec `get_context_data()` surchargée, qui construit
le contexte ci-dessus. Reste `StaffRequisMixin, TemplateView` — pas de changement de garde
d'accès.

## Template

`dashboard_admin.html` :
- Cartes KPI 1 et 2 : chiffres réels via le contexte.
- Cartes KPI 3 et 4 (Séquestre, Revenu) + bloc "Taux de conversion" : remplacés par un
  état "Bientôt disponible" (icône + texte, même emplacement/style de carte, pas de
  fausse donnée).
- Section "Validation en attente" : `{% for annonce in annonces_en_attente %}` sur les
  deux variantes (table desktop + cartes mobile), boutons d'action réels.
- Section "Activité récente" : `{% for evenement in activites_recentes %}`, un seul
  gabarit d'entrée avec icône/couleur conditionnée par `evenement.type`.
- Bouton "Charger plus d'activité" : retiré (pas de pagination pour une v1 sans modèle de
  journal dédié — afficher un bouton qui ne charge rien serait trompeur).

`vendeur_liste.html`/`annonce_liste.html` : remplacent leur `{% block styles %}` dupliqué
par l'include partagé, ajoutent le mobile header + les deux includes de nav avec le bon
`active_nav`, et redessinent leur contenu (tableau vendeurs, liste annonces) avec les
classes du système visuel partagé — logique de boucle et champs de données identiques.

## Tests

- `AdminDashboardView` : test que les compteurs KPI reflètent des `AnnonceMirror`/
  `CompteVendeur` créés en base de test (`vendor_db`), test que la liste "en attente"
  n'affiche que les annonces `en_attente` (pas les publiées/refusées), test que
  l'activité récente combine et trie correctement les deux sources, test que l'accès
  reste réservé au staff (regression sur les tests existants).
- `vendeur_liste.html`/`annonce_liste.html` : tests déjà existants (accès, contenu) —
  vérifier qu'ils passent toujours après le changement de template (pas de nouveau test
  requis pour un changement purement visuel, sauf si le contenu textuel testé change).

## Hors périmètre (explicitement)

- Tout modèle Transaction/Séquestre réel.
- Le bouton "Filtrer" sur la validation en attente.
- La pagination/chargement incrémental de l'activité récente.
- Un vrai modèle de journal d'activité/notification (persistant, avec ses propres types
  d'événements) — le flux composé ici est une solution de contournement basée sur les
  données déjà disponibles, pas une fondation pour un futur système de notifications.

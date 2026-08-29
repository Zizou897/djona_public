# Analyse globale du projet Djona & feuille de route

_Généré le 2026-08-26 — à tenir à jour au fil de l'avancement._

## 1. Ce qu'est le dépôt aujourd'hui

Ce dépôt est actuellement une **bibliothèque de maquettes statiques** (HTML + capture d'écran) pour la plateforme Djona (marketplace de véhicules avec mise en relation acheteur/vendeur, paiement séquestre et back-office de modération), accompagnée d'un **squelette Django vide** créé ce jour.

```
djona_back_office/
├── _assets/                  # design tokens (DESIGN.md) + images sources
├── _utilisateur/             # maquettes du parcours public/acheteur (desktop + mobile)
├── _back_office/             # maquettes du parcours staff/admin (desktop + mobile)
├── core/                     # squelette Django (settings, app, templates) — vide de logique métier
└── plan_d_organisation_djona.md   # plan cible : 5 parcours, ~48 écrans
```

Chaque maquette est un `code.html` autonome (Tailwind chargé via CDN, config dupliquée dans chaque fichier, polices Google Fonts + Material Symbols, images placeholder googleusercontent) accompagné d'un `screen.png`. Il n'y a **aucun gabarit partagé, aucun composant réutilisable, aucune app Django connectée** à ces écrans pour l'instant.

## 2. Constats

- **Couverture des maquettes : 15 écrans livrés sur 48 planifiés (~31 %)**, tous les parcours "Public", "Vendeur" et "Communication & Transaction" du plan sont vides ; seuls des fragments d'"Utilisateur" et la totalité du "Back-Office" existent.
- **Changements non commités dans l'arbre de travail** : `connexion_djona`, `inscription_djona`, `connexion_inscription_djona_mobile`, `contact_support_djona_mobile` apparaissent supprimés alors que `connexion_admin_djona` (desktop + mobile) est nouveau et non suivi — à trancher (renommage volontaire ou suppression accidentelle ?) avant de continuer.
- **Design system non factorisé** : chaque `code.html` réembarque sa propre config Tailwind (copiée-collée de `_assets/djona_automotive_system/DESIGN.md`), ce qui va diverger dès qu'un token change.
- **Aucun modèle de données** : pas d'entités Utilisateur/rôles, Annonce, Transaction, Message, Notification dans `core/src/app/`.
- **`core/` n'est qu'un squelette** : `manage.py` est vide, pas d'environnement virtuel, pas de migration, aucune route ne sert de contenu réel.
- **Pas de README, pas de tests, pas de CI.**

## 3. Tâches

### A. Gouvernance / nettoyage Git
- [ ] Statuer sur les fichiers supprimés (`connexion_djona`, `inscription_djona`, `connexion_inscription_djona_mobile`, `contact_support_djona_mobile`) : restaurer ou confirmer la suppression
- [ ] Commiter `connexion_admin_djona` (desktop + mobile) si conservés
- [ ] Rédiger un `README.md` de dépôt expliquant l'organisation `_assets` / `_utilisateur` / `_back_office` / `core`

### B. Maquettes manquantes (d'après `plan_d_organisation_djona.md`)
**Parcours Public**
- [ ] Accueil (desktop)
- [ ] Recherche & filtres (desktop, mobile, mobile-filtres)
- [ ] Détails véhicule (desktop, mobile)
- [ ] Comparaison (desktop, mobile)
- [ ] Favoris (mobile)

**Parcours Utilisateur**
- [ ] Connexion standard (desktop, mobile) — *à recréer si suppression confirmée*
- [ ] Inscription (desktop, mobile) — *à recréer si suppression confirmée*
- [ ] Contact & support (desktop, mobile) — *mobile à recréer si suppression confirmée*
- [x] Paramètres profil (desktop)
- [x] Tableau de bord acheteur (desktop)

**Parcours Vendeur**
- [ ] Déposer une annonce (desktop, mobile étapes 1 à 4)
- [ ] Mes annonces (desktop, mobile-modifier)
- [ ] Dashboard vendeur (mobile)
- [ ] Vitrine pro (desktop, gestion desktop, gestion mobile)

**Communication & Transaction**
- [ ] Messagerie (desktop, mobile-liste, mobile-chat)
- [ ] Paiement & séquestre (desktop, mobile)
- [ ] Suivi transaction (desktop, mobile)
- [ ] Confirmation (desktop, mobile)
- [ ] Suivi des commandes / mes demandes (desktop)

**Back-Office** — déjà couvert à 100 % (dashboard, validation, utilisateurs, transactions, rapports/KPIs, notifications, desktop + mobile)

### C. Design system / front-end
- [ ] Extraire les tokens de `_assets/djona_automotive_system/DESIGN.md` vers une **config Tailwind unique** (fichier `tailwind.config.js`) au lieu de la dupliquer dans chaque `code.html`
- [ ] Remplacer le CDN `cdn.tailwindcss.com` par un **build Tailwind local** (via `django-tailwind` ou pipeline npm) pour la prod
- [ ] Factoriser les blocs communs (sidebar admin, topbar, cartes KPI) en `templates/app/includes/`
- [ ] Remplacer les images placeholder `googleusercontent` par les assets réels de `_assets/`

### D. Backend Django (`core/`)
- [x] Finaliser le bootstrap : `manage.py`, `migrate` (SQLite dev) — dépendances déjà présentes globalement, `.env` toujours à créer pour la prod
- [x] Page de connexion admin (`/connexion/`) branchée sur l'auth Django réelle (login par username **ou** email via `app/backends.py::EmailOrUsernameBackend`), redirection vers `/admin/` (Jazzmin) après authentification
- [x] Superadmin de développement créé (`admin` / `admin@gmail.com` / mot de passe `admin` — **à changer avant toute mise en production**, mot de passe volontairement faible et validators contournés)
- [x] Dashboard admin (`/tableau-de-bord/`) branché derrière l'auth réelle (`LoginRequiredMixin` + `is_staff`), adapté de la maquette `admin_dashboard_djona` — **chiffres encore statiques**, à remplacer une fois les modèles Annonce/Utilisateur/Transaction créés
- [ ] Convertir les liens de la sidebar dashboard (Validation Queue, Users, Transactions) — actuellement `href="#"`, en attente des vues correspondantes
- [x] Responsive de la connexion admin et du dashboard admin : fond de marque + carte adaptative sur mobile (<768px, repris de la maquette mobile), sidebar/topbar desktop dès `lg` (≥1024px) avec en-tête + nav basse mobile en dessous, tableau de validation → liste de cartes sous `lg`, grille KPI passée à `xl` (1280px) pour éviter le chevauchement au seuil `lg`
- [ ] Modéliser les entités métier dans `app/models.py` (ou apps dédiées) en héritant de `Convention` :
  - [ ] Utilisateur / rôles (acheteur, vendeur particulier, vendeur pro, staff, admin)
  - [ ] Annonce / Véhicule (+ statuts : brouillon, en attente de validation, publiée, refusée)
  - [ ] Transaction / Séquestre (statuts du tunnel de paiement)
  - [ ] Conversation / Message
  - [ ] Notification
  - [ ] Rapport / KPI (ou agrégation calculée)
- [ ] Authentification + gestion des rôles/permissions
- [ ] Convertir chaque maquette validée en couple template Django + vue + route, au fur et à mesure
- [ ] Enregistrer les modèles dans `admin.py` et personnaliser Jazzmin (déjà configuré dans `settings.py`)
- [ ] Workflow de dépôt d'annonce multi-étapes (formulaire ou wizard)
- [ ] Messagerie (a minima polling ; websockets/Channels si temps réel requis)
- [ ] Intégration paiement/séquestre (choix du prestataire à valider avec l'utilisateur)
- [ ] Notifications email (via `core/utils.py::send_customize_email`) + in-app
- [ ] Vues Rapports & KPIs pour le staff

### E. Qualité / Infra
- [ ] Mettre en place des tests (au moins sur les modèles et vues critiques)
- [ ] CI (lint + tests) sur les push/PR
- [ ] Dockerfile / config de déploiement
- [ ] Documentation de contribution (`ARCHITECTURE.md` déjà présent dans `core/`, à compléter avec les apps métier ajoutées)

## 4. Priorisation suggérée

1. Trancher le point Git (A) pour repartir sur une base propre
2. Finaliser le bootstrap Django (D, premiers points) pour avoir un serveur fonctionnel
3. Factoriser le design system (C) avant de multiplier les nouvelles maquettes, pour ne pas dupliquer la dette
4. Compléter les maquettes manquantes prioritaires : parcours Public et Vendeur (B), cœur du produit
5. Brancher progressivement le back-office existant sur de vrais modèles (D)

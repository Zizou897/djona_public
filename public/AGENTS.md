# AGENTS.md — Contexte pour agent IA de code

> Document de contexte destiné à un agent IA de développement (Claude Code, Cursor, etc.).
> Objectif : **migrer les maquettes statiques Djona vers une application réelle Django + HTMX + Tailwind CSS.**
> Lis ce fichier en entier avant toute action. Il décrit l'existant, la cible, le design system, les conventions et le plan de travail.

---

## 1. Le projet en une phrase

**Djona** est une marketplace automobile pour la **Côte d'Ivoire** (interface en **français**) : acheter, vendre et gérer un véhicule avec un tunnel de transaction sécurisé (« Acheter via Djona »). Positionnement : **professionnel, fiable, premium**, mobile-first.

Ce dépôt (`djona_public`) ne contient pour l'instant que le **parcours public** (découverte & recherche). Les autres parcours (utilisateur, vendeur, communication/transaction, back-office) existent sous forme de maquettes ailleurs et seront intégrés plus tard (voir §9).

---

## 2. État actuel du dépôt (ce qui existe)

Ce sont des **maquettes statiques générées par Google Stitch**, pas une application. Aucun backend, aucun build, aucun framework JS.

```
djona_public/
├── .gitignore                      # ⚠️ template Python générique (à adapter, cf. §8)
├── 01_public/
│   ├── desktop/                    # 9 écrans
│   │   ├── djona_accueil/                                   {code.html, screen.png}
│   │   ├── rechercher_un_v_hicule_djona/
│   │   ├── d_tails_du_v_hicule_djona/
│   │   ├── comparaison_de_v_hicules_djona/
│   │   ├── comparaison_de_v_hicules_avec_badges_djona/
│   │   ├── comparaison_de_v_hicules_avec_choix_de_l_expert_djona/
│   │   ├── comparaison_de_v_hicules_avec_rationale_expert_djona/
│   │   ├── comparaison_de_v_hicules_avec_tooltips_djona/
│   │   └── comparaison_de_v_hicules_avec_toutes_les_rationales_djona/
│   └── mobile/                     # 5 écrans
│       ├── recherche_de_v_hicules_djona_mobile/
│       ├── filtres_avanc_s_djona_mobile/
│       ├── d_tails_du_v_hicule_djona_mobile/
│       ├── comparaison_de_v_hicules_djona_mobile/
│       └── mes_favoris_djona_mobile/
└── _assets/
    ├── djona_automotive_system/DESIGN.md   # ✅ design system officiel (source de vérité UI)
    ├── djona_logo.jpg/screen.png           # logo
    └── professional_headshot_.../screen.png # portrait (avatar de démo)
```

Chaque maquette = un `code.html` (HTML complet autonome) + un `screen.png` (rendu de référence).

### Caractéristiques techniques des `code.html`
- **Tailwind via CDN** (`https://cdn.tailwindcss.com`) + un bloc `tailwind.config` **inline dupliqué dans chaque fichier** (mêmes tokens partout).
- Polices **Montserrat** (titres) + **Inter** (corps) via Google Fonts ; icônes **Material Symbols Outlined**.
- Un peu de **JS vanilla** inline (ex. compteurs animés avec `IntersectionObserver` sur l'accueil).
- Attributs `data-path`, `data-active`, `data-alt` : intention de routing/navigation **non câblée** (tous les liens sont `href="#"`).
- `lang="fr"` présent sur `<html>`.

---

## 3. Diagnostic — problèmes à corriger pendant la migration

| # | Problème | Impact | Action attendue |
|---|----------|--------|-----------------|
| 1 | **97 images pointent vers des URL Google temporaires** (`lh3.googleusercontent.com/...`) | 🔴 Critique : elles expireront → images cassées | Télécharger/remplacer par des assets locaux servis par Django (`static/` ou `media/`), ou des placeholders + modèle de données. |
| 2 | **Rien n'est commité** sauf `.gitignore` (seul fichier suivi ; le reste est untracked) | 🟠 Historique git vide | Committer proprement après structuration (cf. §8). |
| 3 | **`.gitignore` = template Python** générique | 🟡 Incohérent avec le contenu actuel, mais **cohérent avec la cible Django** | Conserver la base Python/Django, ajouter Node/Tailwind (`node_modules/`, CSS compilé si versionné). |
| 4 | **Config Tailwind dupliquée** dans les 14 fichiers | 🟠 Non maintenable | Centraliser dans **un seul** `tailwind.config.js` + un template de base Django. |
| 5 | **Tailwind CDN** (mode dev, non purgé) | 🟠 Pas production-ready | Passer à un **build Tailwind** (CLI standalone ou `django-tailwind`). |
| 6 | **Aucune navigation** entre écrans (`href="#"`) | 🟠 Prototypes isolés | Câbler les URLs Django + navigation réelle. |
| 7 | **Desktop et mobile en fichiers séparés** | 🟡 Doublon | **Fusionner** en un seul template **responsive** par écran logique (cf. §5), ne pas garder deux pages. |
| 8 | **5 variantes de la page « comparaison »** (badges, tooltips, rationale expert…) | 🟡 Explorations design | **Consolider en une seule** vue de comparaison reprenant les meilleurs éléments ; ne pas créer 5 pages. |
| 9 | Noms de dossiers avec artefacts d'accents (`d_tails`, `filtres_avanc_s`) | 🟡 Pas URL-friendly | Utiliser des slugs propres pour les routes (cf. §5). |

---

## 4. Architecture cible

**Stack : Django (backend + templates) + HTMX (interactivité) + Tailwind CSS (build).**

Principes :
- **Server-side rendering** avec les templates Django. HTMX pour les interactions dynamiques (filtres, favoris, pagination, comparateur) **sans SPA** ni JS lourd — cohérent avec le style actuel (HTML + micro-JS).
- **Progressive enhancement** : la page fonctionne sans JS, HTMX améliore l'expérience.
- **Un template responsive par écran** (Tailwind `sm:`/`md:`/`lg:`), pas de pages mobile séparées.
- **Tailwind compilé** (pas de CDN) avec les tokens du design system (§6) dans `tailwind.config.js`.
- **Assets locaux** : logo, images véhicules → `static/` (fixtures) puis `media/` (uploads réels).

### Arborescence de projet proposée
```
djona_public/
├── manage.py
├── requirements.txt              # django, htmx (optionnel: django-htmx), django-tailwind ou build CLI
├── config/                       # projet Django (settings, urls, wsgi/asgi)
│   ├── settings/                 # base.py, dev.py, prod.py
│   └── urls.py
├── apps/
│   ├── catalog/                  # véhicules : modèles, vues, urls (listing, détail, comparaison, favoris)
│   └── core/                     # pages générales (accueil, layout, composants partagés)
├── templates/
│   ├── base.html                 # <head>, header, footer, config Tailwind, fonts
│   ├── partials/                 # _header, _footer, _vehicle_card, _filters, _compare_row … (réutilisables + cibles HTMX)
│   ├── core/home.html
│   └── catalog/{list,detail,compare,favorites}.html
├── static/
│   ├── css/                      # input.css (@tailwind) → output compilé
│   ├── img/                      # logo, placeholders, images de démo
│   └── js/                       # htmx.min.js + micro-interactions (compteurs, etc.)
├── theme/                        # config Tailwind si django-tailwind
│   └── tailwind.config.js
└── _mockups/                     # (déplacer ici l'existant 01_public/ + _assets/ comme référence, hors build)
```
> Conserver les maquettes d'origine sous `_mockups/` (ou `docs/mockups/`) comme **référence visuelle**, ne pas les servir.

---

## 5. Inventaire des écrans → routes Django (parcours public)

Fusionner desktop + mobile en un écran logique responsive. 6 écrans logiques :

| Écran logique | Maquettes sources | URL proposée | Vue / template | Interactions HTMX |
|---|---|---|---|---|
| **Accueil** | `djona_accueil` (desktop) | `/` | `core:home` → `core/home.html` | compteurs animés (JS), recherche rapide |
| **Recherche / Listing** | `rechercher_un_v_hicule_djona` (D) + `recherche_de_v_hicules_djona_mobile` (M) | `/vehicules/` | `catalog:list` → `catalog/list.html` | filtres live, pagination, tri (swap de la liste via HTMX) |
| **Filtres avancés** | `filtres_avanc_s_djona_mobile` (M) | (partie de `/vehicules/`) | partial `partials/_filters.html` | offcanvas/modal mobile, applique les filtres sur la liste |
| **Détails véhicule** | `d_tails_du_v_hicule_djona` (D) + `d_tails_du_v_hicule_djona_mobile` (M) | `/vehicules/<slug>/` | `catalog:detail` → `catalog/detail.html` | galerie, ajout favori, ajout au comparateur |
| **Comparaison** | `comparaison_de_v_hicules_djona` + 4 variantes (D) + `comparaison_de_v_hicules_djona_mobile` (M) | `/comparer/` | `catalog:compare` → `catalog/compare.html` | ajout/retrait de véhicules, tooltips, badges « choix expert » |
| **Favoris** | `mes_favoris_djona_mobile` (M) | `/favoris/` | `catalog:favorites` → `catalog/favorites.html` | retrait favori (swap HTMX) |

> Les 5 variantes de comparaison sont des explorations : produire **une seule** page qui intègre badges + tooltips + « choix de l'expert » + rationales.

### Modèle de données minimal (à créer dans `catalog`)
- `Vehicle` : marque, modèle, année, prix, kilométrage, carburant, transmission, localisation (ville), état (Neuf/Occasion), `slug`, `is_verified` (badge « Djona Verified »), vendeur (FK, plus tard).
- `VehicleImage` : FK `Vehicle`, image, ordre.
- `Favorite` : user (ou session) ↔ vehicle.
- (Plus tard) `Comparison`, `Seller`, etc.

---

## 6. Design system (source de vérité : `_assets/djona_automotive_system/DESIGN.md`)

Reprendre **exactement** ces tokens dans `tailwind.config.js`. Le fichier `DESIGN.md` contient le YAML complet ; extraits clés :

### Couleurs (rôles Material 3)
- **Primary — Deep Navy** `#003b5a` (`on-primary` `#ffffff`, `primary-container` `#1a5276`) → headers, navigation, branding, boutons primaires. Évoque la confiance institutionnelle.
- **Secondary/Accent — Vibrant Orange** `secondary-container` `#fea520` (`secondary` `#865300`) → **réservé aux CTA principaux** (« Acheter via Djona »), badges « Djona Verified », highlights critiques.
- **Tertiary — Slate** `#26384b` → icônes, éléments UI secondaires.
- **Surfaces** : background `#f8f9f9`, cartes en blanc pur `#ffffff` ; échelle `surface-container-*` de `#ffffff` à `#e1e3e3`.
- **Texte** : `on-surface` `#191c1c`, `on-surface-variant` `#41474e`. **Outline** `#72787f`, `outline-variant` `#c1c7cf`.
- **Error** `#ba1a1a` / `error-container` `#ffdad6`.

### Typographie
- **Titres : Montserrat** (600/700). Échelle : `display-lg` 48/56 (-0.02em), `headline-lg` 32/40, `headline-md` 24/32, `headline-lg-mobile` 24/32.
- **Corps & UI : Inter** (400–700). `body-lg` 18/28, `body-md` 16/24, `label-md` 14/20 (0.01em, 600), `label-sm` 12/16 (500).
- Règle : le **prix** d'un véhicule (`headline-md`) doit primer sur les specs (`label-sm`).

### Espacement & grille
- Base **8px**. Marges latérales **16px mobile / 32px desktop**, largeur max **1280px**. Gouttière 16px, `section-gap` **48px** (voire 64px entre grandes sections).
- Grille **4 colonnes mobile / 12 colonnes desktop**.

### Formes & élévation
- Rayons : boutons/inputs **8px** (`0.5rem`), cartes/modales **16px** (`1rem`), pills `full`.
- Ombre signature des cartes (teinte bleue) : `box-shadow: 0px 4px 12px rgba(26,82,118,0.08)`. Élévation accrue au hover.
- Icônes : Material Symbols, trait **2px**.

### Composants (specs dans DESIGN.md)
- **Boutons** : Primary (navy/blanc), **Accent** (orange/blanc, uniquement « Acheter via Djona »), Secondary (bordure navy transparente).
- **Cartes véhicule** : image en haut, infos en bas ; bordure douce pour que les voitures blanches ne se fondent pas ; prix = élément le plus proéminent après le titre.
- **Inputs** : labels contrastés, bord 1px `#D5DBDB`, rayon 8px, focus bord 2px navy.
- **Chips/Badges** : Verified = pill orange + check ; tags d'état (« Occasion », « Neuf ») fond gris clair + texte slate.

---

## 7. Conventions pour l'agent

- **Langue** : toute l'UI en **français** (fr-CI). Code, noms de variables et commentaires en anglais ; contenu visible en français.
- **Ne pas réintroduire le CDN Tailwind** : utiliser le build. Un seul `tailwind.config.js`, tokens du §6.
- **HTMX d'abord, JS ensuite** : privilégier `hx-get`/`hx-post`/`hx-swap` + partials Django plutôt que du JS custom. Garder le JS pour les micro-interactions purement visuelles (compteurs, carrousel).
- **Partials réutilisables** : `_vehicle_card.html`, `_filters.html`, etc. Les endpoints HTMX renvoient ces partials.
- **Images** : aucune URL `googleusercontent.com` en dur. Passer par `{% static %}` / `ImageField`. Placeholders locaux tant que les vraies images n'existent pas.
- **Responsive** : un template par écran, breakpoints Tailwind ; interdiction de recréer des pages « mobile » distinctes.
- **Accessibilité** : boutons icône-only → `aria-label` ; conserver `lang="fr"` ; vérifier les contrastes (l'orange accent sur blanc doit rester lisible).
- **Slugs propres** pour les routes (`/vehicules/toyota-corolla-2019/`), pas les noms de dossiers accentués.
- **Commits** petits et thématiques ; messages en français ou anglais, cohérents.

---

## 8. Git & `.gitignore`

- Actuellement seul `.gitignore` est commité (« Initial commit ») ; `01_public/` et `_assets/` sont **non suivis**. La réorganisation desktop/mobile est locale et non commitée.
- Le `.gitignore` est un **template Python** — **le garder** (cible Django) et **compléter** pour Node/Tailwind :
  ```gitignore
  # Django
  *.sqlite3
  /media/
  /staticfiles/
  .env
  # Node / Tailwind
  node_modules/
  # CSS compilé (si non versionné)
  /static/css/output.css
  ```
- Étapes suggérées : structurer le projet Django → déplacer les maquettes sous `_mockups/` → premier commit « scaffold Django + Tailwind build » → commits par écran.

---

## 9. Périmètre global (roadmap au-delà du public)

Le produit complet compte **5 parcours** (les maquettes existent hors de ce dépôt) :
1. **Public** — *présent ici* : accueil, recherche/filtres, détails, comparaison, favoris.
2. **Utilisateur** — connexion, inscription, profil, tableau de bord acheteur, support.
3. **Vendeur** — dépôt d'annonce (4 étapes), mes annonces, dashboard vendeur, vitrine pro.
4. **Communication & Transaction** — messagerie, paiement/séquestre, suivi de transaction, confirmation.
5. **Back-office (Staff/Admin)** — validation d'annonces, gestion utilisateurs/transactions, KPIs, notifications.

Concevoir l'architecture Django (apps, auth, modèles) pour **accueillir ces parcours** ensuite, même si seul le public est implémenté d'abord. Le tunnel « Acheter via Djona » (paiement séquestre) est le différenciateur central du produit.

---

## 10. Prochaines étapes (ordre recommandé)

1. **Scaffold** : projet Django (`config/`), apps `core` + `catalog`, `requirements.txt`, settings dev/prod.
2. **Tailwind build** : intégrer `tailwind.config.js` avec les tokens §6, `input.css`, pipeline de compilation ; brancher fonts + Material Symbols.
3. **`base.html`** : header/footer extraits des maquettes, responsive, HTMX chargé.
4. **Accueil** (`/`) : porter `djona_accueil` en template + partials + compteurs.
5. **Catalog** : modèle `Vehicle` + fixtures de démo (assets locaux) → **listing** `/vehicules/` (filtres/pagination HTMX) → **détail** `/vehicules/<slug>/`.
6. **Comparaison** consolidée `/comparer/` + **favoris** `/favoris/` (HTMX).
7. **Nettoyage** : supprimer les URLs Google, déplacer les maquettes sous `_mockups/`, `.gitignore` à jour, commits.
8. **Vérif** : responsive desktop/mobile conforme aux `screen.png`, pas de CDN, pas d'image externe, a11y de base.

# Réorganisation en monorepo `djona_public/{public,vendor,admin}` — Design

## Contexte

Le projet Djona vit aujourd'hui dans **trois dépôts git séparés** sur la même machine :

- `djona_public` — parcours public/acheteur (catalogue, favoris, comparateur), Django +
  Tailwind + HTMX, dépôt actif avec du travail en cours (une autre session Claude,
  `djona-public-83`, y travaille en ce moment).
- `djona_back_office` (ce dépôt) — contient `admin/` (backoffice staff) et `vendor/`
  (portail vendeur), chacun un projet Django complet sous sa propre structure
  `<projet>/core/src/`.
- (`djona_vendor` existe aussi comme dossier séparé sur la machine mais n'est pas
  concerné ici — `vendor/` dans `djona_back_office` est la copie de travail actuelle.)

L'utilisateur veut regrouper ces trois parcours dans **un seul dépôt monorepo**,
`djona_public`, réorganisé en trois sous-dossiers `public/`, `vendor/`, `admin/`, chacun
représentant un projet Django indépendant et autonome (comme c'est déjà le cas pour
`admin/` et `vendor/` dans `djona_back_office`).

## Décisions déjà validées avec l'utilisateur

- **Contenu actuel de `djona_public`** (tout ce qui est aujourd'hui à sa racine : `apps/`,
  `config/`, `templates/`, `static/`, `manage.py`, etc.) est déplacé tel quel dans un
  nouveau sous-dossier `djona_public/public/`.
- **Historique git** : pas de préservation d'historique (pas de `git subtree`/
  `filter-repo`). Copie simple des fichiers de `admin/` et `vendor/` dans `djona_public`
  (qui a déjà son propre historique git pour le contenu `public/`), puis nouveau commit.
  `djona_back_office` n'est pas supprimé, il reste tel quel en local.
- **Timing** : attendre que `djona-public-83` ait committé son travail en cours avant de
  toucher à quoi que ce soit dans `djona_public`.
- **`docs/` et `.superpowers/`** (racine de `djona_back_office`, contenu de planification
  de session, pas propre à un seul projet) → déplacés dans `admin/docs/` et
  `admin/.superpowers/`.
- **Identifiants MySQL Aiven en clair** dans `djona_public/config/settings/dev.py` (non
  committés) → sortis vers `.env` pendant cette réorganisation, avec le même pattern
  `python-decouple` déjà utilisé par `admin/`/`vendor/`.
- **venv/node_modules/** : pas copiés, recréés après coup (`pip install`/`npm install`
  sur place). `db.sqlite3` de chaque projet copié tel quel s'il contient des données
  utiles (celui d'`admin`/`vendor` semble vide — MySQL est déjà utilisé — celui de
  `public` peut contenir des données de catalogue réelles).

## Pourquoi un simple déplacement de dossiers ne casse rien

Point soulevé par `djona-public-83` (à juste titre en théorie, mais qui ne s'applique
pas ici) : les chemins Python (`INSTALLED_APPS`, `ROOT_URLCONF`,
`DJANGO_SETTINGS_MODULE`) sont bien absolus, mais ils sont résolus **relativement à
l'endroit d'où `manage.py` est exécuté** (Django insère le dossier de `manage.py` dans
`sys.path[0]`). Tant que chaque projet est déplacé **en bloc, intact** (tout son
contenu interne ensemble, sans rien déplacer à l'intérieur), aucune référence Python
(`apps.catalog`, `config.settings.dev`, etc.) n'a besoin de changer — exactement comme
`admin/core/src/` et `vendor/core/src/` fonctionnent déjà aujourd'hui dans
`djona_back_office` sans configuration Python spéciale : on fait juste
`cd admin/core/src && python manage.py ...`.

Seuls les fichiers qui contiennent des **chemins absolus vers le système de fichiers**
(scripts de déploiement, configuration nginx/systemd) doivent être mis à jour.

## Structure finale visée

```
djona_public/                      (dépôt git existant, réutilisé)
├── .gitignore                     (remplacé par le .gitignore générique multi-projets
│                                    de djona_back_office — voir section dédiée)
├── public/                        (tout le contenu actuel de djona_public/, déplacé tel quel)
│   ├── .gitignore                 (ex-.gitignore actuel de djona_public, inchangé)
│   ├── manage.py
│   ├── config/
│   ├── apps/
│   ├── templates/
│   ├── static/ , static_cdn/ , media_cdn/
│   ├── deploy/                    (deploy.sh, gunicorn/djona.service, nginx/djona.tech.conf
│   │                                — 3 fichiers avec chemins absolus à mettre à jour)
│   ├── db.sqlite3                 (conservé si données réelles)
│   ├── requirements.txt, package.json, tailwind.config.js, _mockups/, images/, *.md
│   └── (venv/, node_modules/, .venv/ : non copiés — à recréer)
├── vendor/                        (copie intacte de djona_back_office/vendor/)
│   └── core/src/... (inchangé, y compris son propre .gitignore)
└── admin/                         (copie intacte de djona_back_office/admin/)
    ├── core/src/... (inchangé, y compris son propre .gitignore)
    ├── docs/                      (ex-docs/ racine de djona_back_office)
    └── .superpowers/              (ex-.superpowers/ racine de djona_back_office)
```

`_utilisateur/`, `_back_office/`, `_assets/` (maquettes) déjà présents sous `admin/` et
`vendor/` voyagent avec ces dossiers sans changement.

## Étapes de la réorganisation

1. **Attendre la confirmation** de `djona-public-83` que son travail est committé.
2. **`.gitignore` racine de `djona_public`** : remplacé par le `.gitignore` générique
   actuel de `djona_back_office` (déjà conçu pour un monorepo multi-projets — patterns
   non ancrés à la racine, donc valables quel que soit le sous-dossier).
3. **Créer `djona_public/public/`**, y déplacer tout le contenu actuel de la racine de
   `djona_public` (sauf `.git/`, le nouveau `.gitignore` racine, et
   `venv`/`node_modules`/`__pycache__` qui ne sont de toute façon pas versionnés).
4. **Remédiation des identifiants** dans `djona_public/public/config/settings/dev.py` :
   remplacer les valeurs `DATABASES` en dur par des appels `config('MYSQL_...')`
   (pattern `python-decouple` déjà utilisé), mettre à jour
   `djona_public/public/.env` (déjà gitignoré, non exposé) avec les vraies valeurs Aiven
   actuellement en dur dans `dev.py` (pour ne pas changer le comportement actuel), et
   créer `djona_public/public/.env.example` avec des valeurs vides/placeholder (à
   committer, pattern déjà utilisé par `admin/`/`vendor/`).
5. **Mettre à jour les 3 fichiers de déploiement** (`deploy/deploy.sh`,
   `deploy/gunicorn/djona.service`, `deploy/nginx/djona.tech.conf`) : tous les chemins
   `/var/www/project/djona_public/...` deviennent
   `/var/www/project/djona_public/public/...`.
6. **Copier `djona_back_office/vendor/`** intact vers `djona_public/vendor/` (fichiers
   versionnés uniquement — pas de `venv/`, `__pycache__/`, `db.sqlite3` généré par les
   tests, etc.).
7. **Copier `djona_back_office/admin/`** intact vers `djona_public/admin/`, puis
   `djona_back_office/docs/` → `djona_public/admin/docs/` et
   `djona_back_office/.superpowers/` → `djona_public/admin/.superpowers/`.
8. **Vérification** : dans `djona_public`, recréer les 3 environnements (`pip install`
   pour `public/`, `admin/core/`, `vendor/core/` ; `npm install` pour `public/`), lancer
   `manage.py check` (les 3 projets) et la suite de tests `admin`/`vendor` pour confirmer
   que rien n'a été cassé par le déplacement. Démarrer chaque `runserver` brièvement pour
   confirmer qu'ils démarrent bien depuis leur nouvel emplacement.
9. **Commit** dans le dépôt git `djona_public` (un ou plusieurs commits, à définir dans
   le plan).

## Hors périmètre (explicitement)

- Préserver l'historique git de `admin/`/`vendor/` dans le nouveau dépôt.
- Supprimer ou archiver `djona_back_office` après la copie.
- Copier `venv/`, `node_modules/`, `.venv/` (recréés après coup).
- Toute autre modification fonctionnelle du code (cette réorganisation ne touche que
  l'emplacement des fichiers, les chemins de déploiement, et l'extraction des
  identifiants Aiven vers `.env`).
- Réconcilier `djona_vendor` (dossier séparé sur la machine, non lié à cette tâche).

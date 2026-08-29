# Architecture — core (vendeur)

Structure standard d'un projet Django selon l'architecture LouhSira.

Ce projet est le **backoffice vendeur** de Djona : distinct et indépendant du
portail admin (`admin/core/`). Les deux projets ne partagent que la base de
données — chacun a ses propres settings, son propre serveur, son propre code.

```
core/
├── .gitignore
├── requirements.txt
├── ARCHITECTURE.md
├── .env.example
└── src/
    ├── manage.py
    ├── core/
    │   ├── __init__.py
    │   ├── settings.py       # configuration du projet
    │   ├── urls.py            # routes racines
    │   ├── wsgi.py
    │   ├── asgi.py
    │   ├── constants.py       # constantes globales (chemins d'upload, etc.)
    │   └── utils.py           # utilitaires transverses (email, IP, ...)
    ├── app/
    │   ├── __init__.py
    │   ├── models.py          # `Convention` + `Utilisateur` (AUTH_USER_MODEL)
    │   ├── managers.py        # `UtilisateurManager`
    │   ├── validators.py      # validateur de complexité du mot de passe
    │   ├── forms.py           # inscription / connexion
    │   ├── views.py
    │   ├── urls.py
    │   ├── admin.py
    │   ├── apps.py
    │   ├── functions.py       # logique métier réutilisable
    │   └── templatetags/
    │       ├── __init__.py
    │       └── custom_tags.py
    ├── templates/
    │   ├── app/
    │   │   ├── base/           # gabarits de base (base.html)
    │   │   ├── layout/         # pages principales (inscription, connexion, ...)
    │   │   └── includes/       # fragments réutilisables
    │   └── emails/             # gabarits d'e-mails
    ├── static/
    │   └── app/
    │       └── assets/
    │           ├── css/
    │           └── img/
    ├── static_cdn/             # collecté par collectstatic (non versionné)
    ├── media_cdn/              # fichiers uploadés (non versionné)
    └── data/                   # fixtures / imports de données
```

## Conventions

- `app/` contient le contenu éditorial, l'authentification vendeur et les vues génériques du site.
- Chaque app métier ajoutée plus tard (ex : `annonces`, `vitrine`) est déclarée dans son propre dossier au même niveau que `app/`, et ajoutée à `LOCAL_APPS` (`src/core/settings.py`).
- Tous les modèles publiables héritent du modèle abstrait `Convention` (`src/app/models.py`), qui fournit `created_at`, `update_at` et `publish`.
- L'utilisateur vendeur (`app.Utilisateur`) est un modèle utilisateur Django personnalisé (`AUTH_USER_MODEL`), authentifié par email — indépendant du modèle `User` du projet admin.
- La base de données bascule entre SQLite (développement) et MySQL (production) via la variable `USE_MYSQL` dans `.env`.
- `.env`, `db.sqlite3`, `static_cdn/` et `media_cdn/` ne sont jamais versionnés.

## Prochaines étapes

1. `cd core/src && django-admin startproject core .` (si `manage.py` est vide)
2. `pip install -r ../requirements.txt`
3. Copier `.env.example` → `.env` et renseigner les valeurs
4. `python manage.py migrate`
5. `python manage.py runserver`

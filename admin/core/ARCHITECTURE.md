# Architecture — core

Structure standard d'un projet Django selon l'architecture LouhSira.

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
    │   ├── models.py          # contient le modèle abstrait `Convention`
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
    │   │   ├── layout/         # pages principales (index.html, ...)
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

- `app/` contient le contenu éditorial et les vues génériques du site.
- Chaque app métier (ex : `produit`, `commande`, `reservation`) est ajoutée séparément dans son propre dossier au même niveau que `app/`, et déclarée dans `LOCAL_APPS` (`src/core/settings.py`).
- Tous les modèles publiables héritent du modèle abstrait `Convention` (`src/app/models.py`), qui fournit `created_at`, `update_at` et `publish`.
- La base de données bascule entre SQLite (développement) et MySQL (production) via la variable `USE_MYSQL` dans `.env`.
- `.env`, `db.sqlite3`, `static_cdn/` et `media_cdn/` ne sont jamais versionnés.

## Prochaines étapes

1. `cd core/src && django-admin startproject core .` (si `manage.py` est vide)
2. `pip install -r ../requirements.txt`
3. Copier `.env.example` → `.env` et renseigner les valeurs
4. `python manage.py migrate`
5. `python manage.py runserver`

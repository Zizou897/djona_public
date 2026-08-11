# ARCHITECTURE.md — Djona (parcours public)

Stack : **Django 5 + HTMX + Tailwind CSS (build CLI)**. Voir `AGENTS.md` pour le
contexte complet (diagnostic, roadmap, design system).

## Arborescence

```
djona_public/
├── manage.py
├── requirements.txt              # django, django-htmx, pillow, python-decouple
├── package.json                  # tailwindcss (CLI standalone, pas de CDN)
├── tailwind.config.js            # tokens repris de _mockups/_assets/djona_automotive_system/DESIGN.md
├── .env.example
├── config/                       # projet Django
│   ├── settings/
│   │   ├── base.py               # commun
│   │   ├── dev.py                # sqlite, DEBUG=True
│   │   └── prod.py               # mysql, sécurité durcie
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/                     # pages générales : accueil, layout, header/footer
│   │   ├── views.py
│   │   └── urls.py
│   └── catalog/                  # véhicules (à implémenter : listing, détail, comparaison, favoris)
│       └── models.py             # Convention (abstrait) pour l'instant
├── templates/
│   ├── base.html                 # <head>, header, <main>, config fonts/Tailwind
│   ├── partials/
│   │   └── _header.html          # header public (1ère vue portée depuis les maquettes)
│   └── core/
│       └── home.html
├── static/
│   ├── css/
│   │   ├── input.css             # source @tailwind
│   │   └── output.css            # généré par `npm run build:css` (non versionné)
│   ├── img/
│   │   └── djona-logo.png        # logo local (remplace l'URL googleusercontent des maquettes)
│   └── js/
├── static_cdn/ , media_cdn/       # collectstatic / uploads (non versionnés)
└── _mockups/                      # maquettes Google Stitch d'origine, référence visuelle uniquement
    ├── 01_public/                 # desktop/ + mobile/ (code.html + screen.png par écran)
    └── _assets/djona_automotive_system/DESIGN.md   # design system source de vérité
```

## État d'avancement

- [x] Scaffold Django (`config/`, `apps/core`, `apps/catalog`)
- [x] Build Tailwind (tokens du design system, pas de CDN)
- [x] `base.html` + header public (`partials/_header.html`) — **première vue livrée**
- [x] Footer (`partials/_footer.html`, inclus dans `base.html`)
- [x] Accueil complet (hero, recherche, listings, trust bar, CTA vente, stats animées)
- [ ] Catalogue : modèles `Vehicle`/`VehicleImage`/`Favorite` + listing/détail/comparaison/favoris

## Démarrage local

```bash
python -m venv .venv
./.venv/Scripts/activate           # Windows
pip install -r requirements.txt
npm install
npm run build:css                  # ou npm run watch:css en développement
cp .env.example .env                # puis renseigner SECRET_KEY etc.
python manage.py migrate
python manage.py runserver
```

## Conventions

Voir `AGENTS.md` §7 : HTMX d'abord (JS uniquement pour le micro-interactif),
partials réutilisables, aucune image externe (`{% static %}`/`ImageField`
uniquement), un seul template responsive par écran, `lang="fr"`, slugs propres.

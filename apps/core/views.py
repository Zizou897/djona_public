from django.shortcuts import render


def home(request):
    """Page d'accueil du parcours public.

    Pour l'instant, seul le header (partials/_header.html) est intégré.
    Le reste de la page (hero, recherche, listings...) sera porté depuis
    _mockups/01_public/desktop/djona_accueil/code.html dans une prochaine étape.
    """
    return render(request, 'core/home.html', {})

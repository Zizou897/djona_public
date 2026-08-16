from django.http import HttpResponse
from django.shortcuts import render

from apps.catalog.models import Vehicle

HOME_STATS = [
    {'end': 1450, 'suffix': '+', 'label': 'Véhicules vendus'},
    {'end': 2300, 'suffix': '', 'label': 'Clients heureux'},
    {'end': 150, 'suffix': '', 'label': "Points d'inspection"},
    {'end': 5000, 'suffix': 'h', 'label': "Heures d'accompagnement"},
]


def home(request):
    """Page d'accueil du parcours public, portée depuis
    _mockups/01_public/desktop/djona_accueil/code.html.
    """
    context = {
        'featured_vehicles': Vehicle.objects.filter(publish=True).prefetch_related('images').order_by('-is_verified', '-created_at')[:6],
        'stats': HOME_STATS,
    }
    return render(request, 'core/home.html', context)


FAQ_ITEMS = [
    {
        'question': 'Comment Djona vérifie-t-elle les véhicules ?',
        'answer': "Chaque véhicule listé sur Djona subit une inspection rigoureuse sur 150 points de contrôle par nos techniciens certifiés. Nous vérifions l'historique administratif, l'état mécanique et la carrosserie avant toute mise en ligne.",
    },
    {
        'question': 'Le paiement est-il sécurisé ?',
        'answer': "Absolument. Djona utilise un système de compte séquestre. Les fonds ne sont débloqués au vendeur que lorsque l'acheteur a validé la conformité du véhicule après l'essai final et la vérification des documents.",
    },
    {
        'question': 'Quels sont les frais de service Djona ?',
        'answer': "Notre commission est transparente et varie selon la valeur du véhicule. Elle couvre l'inspection, la sécurisation du paiement et l'assistance administrative pour le transfert de propriété.",
    },
    {
        'question': 'Puis-je obtenir un financement via Djona ?',
        'answer': "Oui, nous collaborons avec plusieurs banques partenaires en Côte d'Ivoire pour vous proposer des solutions de crédit automobile adaptées à votre profil directement depuis notre plateforme.",
    },
]


def contact(request):
    """Page contact / support, portée depuis
    _mockups/01_public/desktop/contact_support_djona/code.html.
    """
    return render(request, 'core/contact.html', {'faq_items': FAQ_ITEMS})


def privacy(request):
    """Politique de confidentialité, portée depuis
    _mockups/01_public/desktop/conditions/screen.png (pas de code.html source).
    """
    return render(request, 'core/privacy.html')


def terms(request):
    """Conditions Générales d'Utilisation, portée depuis
    _mockups/01_public/desktop/conditions/code.html (source fournie par l'utilisateur).
    """
    return render(request, 'core/terms.html')


def seller_terms(request):
    """Conditions Particulières Vendeurs, portée depuis une maquette fournie
    directement par l'utilisateur (source non stockée dans _mockups/).
    """
    return render(request, 'core/seller_terms.html')


def robots_txt(request):
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        '',
        f'Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')

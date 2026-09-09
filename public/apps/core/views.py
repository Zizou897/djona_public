from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Vehicle

from .forms import NewsletterForm
from .models import NewsletterSubscriber

NEWSLETTER_RATE_LIMIT = 5
NEWSLETTER_RATE_WINDOW = 600  # secondes (10 min)

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
        'featured_vehicles': Vehicle.objects.filter(publish=True).prefetch_related('images').order_by('-is_verified', '-created_at')[:8],
        'stats': HOME_STATS,
        'search_brands': Vehicle.objects.filter(publish=True).values_list('brand', flat=True).distinct().order_by('brand'),
        'search_cities': Vehicle.objects.filter(publish=True).values_list('city', flat=True).distinct().order_by('city'),
    }
    return render(request, 'core/home.html', context)


def about(request):
    """Page À propos de Djona, portée depuis
    _mockups/01_public/desktop/about/code.html.
    """
    return render(request, 'core/about.html')



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


def _client_ip(request):
    # X-Real-IP posé par nginx en prod (voir deploy/nginx/djona.tech.conf) —
    # plus fiable que X-Forwarded-For, qu'un client peut usurper directement
    # s'il n'est pas nettoyé. REMOTE_ADDR suffit en local (pas de proxy).
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', 'unknown')


@require_POST
def newsletter_subscribe(request):
    """Inscription newsletter — formulaire dans le footer, présent sur toutes
    les pages. Répond en JSON pour l'appel fetch() du footer (static/js/newsletter.js,
    popup SweetAlert2 + pas de rechargement) ; retombe sur une redirection classique
    avec django.contrib.messages si JS est désactivé.

    Rate-limité par IP (cache partagé entre workers gunicorn, voir CACHES dans
    settings) pour empêcher un script de spammer la table des abonnés.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    cache_key = f'newsletter-subscribe:{_client_ip(request)}'
    attempts = cache.get(cache_key, 0)
    if attempts >= NEWSLETTER_RATE_LIMIT:
        status, message = 'error', 'Trop de tentatives — réessayez dans quelques minutes.'
        if is_ajax:
            return JsonResponse({'status': status, 'message': message}, status=429)
        messages.error(request, message)
        return redirect(request.META.get('HTTP_REFERER') or 'core:home')
    cache.set(cache_key, attempts + 1, NEWSLETTER_RATE_WINDOW)

    form = NewsletterForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data['email']
        subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email)
        was_inactive = not subscriber.is_active
        if was_inactive:
            subscriber.is_active = True
            subscriber.save(update_fields=['is_active'])

        if created or was_inactive:
            status, message = 'success', 'Merci ! Vous êtes désormais abonné à la newsletter Djona.'
        else:
            status, message = 'info', 'Vous êtes déjà abonné avec cette adresse.'
    else:
        status, message = 'error', "Adresse email invalide — vérifiez et réessayez."

    if is_ajax:
        return JsonResponse({'status': status, 'message': message})

    getattr(messages, status)(request, message)
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer or 'core:home')

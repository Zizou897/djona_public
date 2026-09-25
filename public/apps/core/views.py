from django.contrib import messages
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Vehicle

from .forms import NewsletterForm, TransportRequestForm
from .models import NewsletterSubscriber, TransportRequest

NEWSLETTER_RATE_LIMIT = 5
NEWSLETTER_RATE_WINDOW = 600  # secondes (10 min)
TRANSPORT_RATE_LIMIT = 5
TRANSPORT_RATE_WINDOW = 3600  # secondes (1 h)
NL = chr(10)

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
    fuel_labels = dict(Vehicle.FuelType.choices)
    brand_options = {}
    for brand, fuel_type, city in (
        Vehicle.objects.filter(publish=True)
        .values_list('brand', 'fuel_type', 'city')
        .distinct()
    ):
        entry = brand_options.setdefault(brand, {'fuel_types': {}, 'cities': set()})
        entry['fuel_types'][fuel_type] = fuel_labels.get(fuel_type, fuel_type)
        entry['cities'].add(city)

    search_brand_options = {
        brand: {
            'fuel_types': [
                {'value': value, 'label': label}
                for value, label in sorted(data['fuel_types'].items(), key=lambda item: item[1])
            ],
            'cities': sorted(data['cities']),
        }
        for brand, data in brand_options.items()
    }

    context = {
        'featured_vehicles': Vehicle.objects.filter(publish=True).prefetch_related('images').order_by('-is_verified', '-created_at')[:8],
        'stats': HOME_STATS,
        'search_brands': sorted(brand_options.keys()),
        'search_brand_options': search_brand_options,
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


def _notify_transport_request(transport_request):
    """Notifie l'équipe Djona (et le contact transport du partenaire) par email.
    Destinataires dans settings.TRANSPORT_NOTIFY_EMAILS ; sans effet si vide.
    Ne doit jamais faire échouer la soumission : la demande est déjà enregistrée
    et visible dans le back-office.
    """
    recipients = getattr(settings, 'TRANSPORT_NOTIFY_EMAILS', [])
    if not recipients:
        return
    who = f'{transport_request.first_name} {transport_request.last_name}'
    if transport_request.company_name:
        who += f' ({transport_request.company_name})'
    body = NL.join([
        f'Nouvelle demande de transport {transport_request.reference}',
        '',
        f'Demandeur : {who}',
        f'Téléphone : {transport_request.phone}',
        f'Email : {transport_request.email or "—"}',
        f'Véhicule : {transport_request.quantity} x {transport_request.vehicle_type}',
        f'Chargement : {transport_request.loading_place} le {transport_request.loading_date:%d/%m/%Y}',
        f'Livraison : {transport_request.delivery_place}',
        '',
        f'Message : {transport_request.message or "—"}',
    ])
    try:
        send_mail(
            f'Nouvelle demande de transport {transport_request.reference}',
            body, None, recipients, fail_silently=True,
        )
    except Exception:
        pass


def transport(request):
    """Page Transport & Logistique : présentation du service et formulaire de
    demande. Djona collecte la demande ; l'exécution est gérée par le partenaire.
    """
    if request.method == 'POST':
        cache_key = f'transport-request:{_client_ip(request)}'
        attempts = cache.get(cache_key, 0)
        if attempts >= TRANSPORT_RATE_LIMIT:
            messages.error(request, 'Trop de demandes envoyées — réessayez plus tard.')
            form = TransportRequestForm(request.POST)
        else:
            form = TransportRequestForm(request.POST)
            if form.is_valid():
                cache.set(cache_key, attempts + 1, TRANSPORT_RATE_WINDOW)
                transport_request = form.save()
                _notify_transport_request(transport_request)
                request.session['transport_reference'] = transport_request.reference
                return redirect('core:transport_success')
    else:
        form = TransportRequestForm()
    return render(request, 'core/transport.html', {'form': form})


def transport_success(request):
    reference = request.session.pop('transport_reference', None)
    if not reference:
        return redirect('core:transport')
    return render(request, 'core/transport_success.html', {'reference': reference})

from django.contrib import messages
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Vehicle

from .forms import ContactMessageForm, NewsletterForm, TransportRequestForm
from .models import ContactMessage, NewsletterSubscriber, SiteContact, TransportRequest

NEWSLETTER_RATE_LIMIT = 5
NEWSLETTER_RATE_WINDOW = 600  # secondes (10 min)
TRANSPORT_RATE_LIMIT = 5
TRANSPORT_RATE_WINDOW = 3600  # secondes (1 h)
CONTACT_RATE_LIMIT = 5
CONTACT_RATE_WINDOW = 3600  # secondes (1 h)

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


AVANTAGES_ITEMS = [
    {
        'icon': 'support_agent',
        'title': 'Un accompagnement personnalisé de votre achat',
        'text': "Acheter un véhicule représente un investissement important. Avec Djona, le client bénéficie d'un accompagnement à chaque étape : analyse du véhicule, compréhension de l'annonce, échanges avec le vendeur et suivi jusqu'à la finalisation de l'achat.",
        'highlight': 'Votre projet d’achat est suivi par un interlocuteur Djona.',
    },
    {
        'icon': 'fact_check',
        'title': "Une meilleure visibilité sur l'état réel du véhicule",
        'text': "Djona accompagne le client afin de mieux comprendre le véhicule qui l'intéresse : vérification des informations annoncées, contrôle des éléments essentiels, identification des points d'attention et aide à la prise de décision.",
        'highlight': "Objectif : permettre au client d'acheter en connaissance de cause.",
    },
    {
        'icon': 'verified_user',
        'title': 'Une transaction plus sécurisée',
        'text': "Avec Djona, l'acheteur bénéficie d'un cadre plus structuré : vendeur identifié, informations mieux suivies, accompagnement dans les échanges et réduction des risques liés aux mauvaises surprises.",
    },
    {
        'icon': 'handshake',
        'title': 'Un accompagnement dans la négociation',
        'text': "Djona aide le client à évaluer la cohérence du prix, identifier les arguments de négociation et faciliter les échanges avec le vendeur afin de réaliser un achat au juste prix.",
    },
    {
        'icon': 'redeem',
        'title': "Des avantages exclusifs après l'achat",
        'text': "Acheter via Djona permet d'intégrer un écosystème automobile : offres préférentielles sur certains services, réductions possibles sur certaines pièces automobiles, conseils et suivi du véhicule, rappels d'entretien.",
    },
    {
        'icon': 'history',
        'title': 'Un historique et un suivi du véhicule',
        'text': "L'achat peut être enregistré dans l'espace personnel Djona : véhicule acheté, date d'acquisition, informations principales, historique des interventions et documents importants.",
    },
    {
        'icon': 'hub',
        'title': 'Un accès facilité aux solutions automobiles',
        'text': "À travers son réseau, Djona pourra accompagner ses clients pour l'assurance automobile, le financement, l'entretien, la réparation, les pièces détachées et les services liés au véhicule.",
    },
]

AVANTAGES_COMPARAISON = [
    ('Seul face au vendeur', "Accompagnement d'un interlocuteur Djona"),
    ('Informations parfois difficiles à vérifier', 'Processus plus structuré'),
    ('Négociation individuelle', 'Assistance dans les échanges'),
    ('Risque de mauvaises surprises', 'Meilleure visibilité avant achat'),
    ('Relation terminée après achat', 'Suivi et avantages dans le temps'),
]

AVANTAGES_CHECKLIST = [
    'Un véhicule mieux évalué',
    'Une transaction plus sereine',
    'Un accompagnement personnalisé',
    'Des avantages exclusifs après achat',
    'Un suivi automobile dans la durée',
]


def avantages(request):
    """Page « Les avantages d'acheter avec Djona » — proposition de valeur
    client portée depuis public/Avantages_Acheter_avec_Djona.docx (contenu
    officiel fourni par l'équipe Djona, pas une maquette)."""
    context = {
        'items': AVANTAGES_ITEMS,
        'comparaison': AVANTAGES_COMPARAISON,
        'checklist': AVANTAGES_CHECKLIST,
    }
    return render(request, 'core/avantages.html', context)



FAQ_ITEMS = [
    {
        'question': 'Comment Djona vérifie-t-elle les véhicules ?',
        'answer': "Djona accompagne l'acheteur pour mieux comprendre le véhicule qui l'intéresse : vérification des informations annoncées, contrôle des éléments essentiels et identification des points d'attention, pour acheter en connaissance de cause.",
    },
    {
        'question': 'Le paiement est-il sécurisé ?',
        'answer': "Avec Djona, l'acheteur bénéficie d'un cadre plus structuré : vendeur identifié, informations mieux suivies et accompagnement dans les échanges, pour réduire les risques liés aux mauvaises surprises.",
    },
    {
        'question': 'Quels sont les frais de service Djona ?',
        'answer': "Le client ne paie pas pour simplement trouver un véhicule : il bénéficie d'un accompagnement qui réduit son risque, améliore sa décision d'achat et crée une relation durable autour de son automobile.",
    },
    {
        'question': 'Puis-je obtenir un financement via Djona ?',
        'answer': "À travers son réseau, Djona pourra accompagner ses clients pour l'assurance automobile, le financement, l'entretien et les autres services liés au véhicule.",
    },
]


def contact(request):
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        cache_key = f'contact-message:{_client_ip(request)}'
        attempts = cache.get(cache_key, 0)
        if attempts >= CONTACT_RATE_LIMIT:
            messages.error(request, 'Trop de messages envoyés — réessayez plus tard.')
        elif form.is_valid():
            cache.set(cache_key, attempts + 1, CONTACT_RATE_WINDOW)
            contact_message = form.save()
            _notify_contact_message(contact_message)
            request.session['contact_sent'] = contact_message.full_name
            return redirect('core:contact_success')
    else:
        form = ContactMessageForm()
    return render(request, 'core/contact.html', {
        'form': form,
        'faq_items': FAQ_ITEMS,
        'contact': SiteContact.load(),
    })


def contact_success(request):
    full_name = request.session.pop('contact_sent', None)
    if not full_name:
        return redirect('core:contact')
    return render(request, 'core/contact_success.html', {'full_name': full_name, 'contact': SiteContact.load()})


def _notify_contact_message(contact_message):
    """Ne doit jamais faire échouer l'envoi : le message est déjà enregistré
    et lisible dans le back-office."""
    recipients = getattr(settings, 'CONTACT_NOTIFY_EMAILS', [])
    if not recipients:
        return
    body = NL.join([
        f'Nouveau message de contact — {contact_message.get_subject_display()}',
        '',
        f'Nom : {contact_message.full_name}',
        f'Téléphone : {contact_message.phone}',
        f'Email : {contact_message.email or "—"}',
        '',
        contact_message.message,
    ])
    try:
        send_mail(
            f'Contact Djona : {contact_message.get_subject_display()} — {contact_message.full_name}',
            body, None, recipients, fail_silently=True,
        )
    except Exception:
        pass


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


def pieces(request):
    return render(request, 'core/pieces.html')


def transport_success(request):
    reference = request.session.pop('transport_reference', None)
    if not reference:
        return redirect('core:transport')
    return render(request, 'core/transport_success.html', {'reference': reference})

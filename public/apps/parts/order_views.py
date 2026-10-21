from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.views import _client_ip

from . import cart as cart_service
from .forms import PartOrderForm, PartTrackingForm
from .models import DeliveryZone, Part, PartOrder, PartsSettings

NL = chr(10)
ORDER_RATE_LIMIT = 5
ORDER_RATE_WINDOW = 3600  # 1 h
TRACK_RATE_LIMIT = 15
TRACK_RATE_WINDOW = 3600


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _cart_context(request, **extra):
    summary = cart_service.summary(request)
    return {'cart': summary, 'parts_cart_count': summary.count, **extra}


def cart_view(request):
    context = _cart_context(request)
    for issue in context['cart'].issues:
        messages.warning(request, issue)
    return render(request, 'parts/cart.html', context)


@require_POST
def cart_add(request, pk):
    part = get_object_or_404(Part.objects.marketplace(), pk=pk)
    if not cart_service.orderable(part):
        message = f'« {part.name} » est indisponible : elle ne peut pas être commandée.'
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'message': message}, status=409)
        messages.error(request, message)
        return redirect(part.get_absolute_url())
    quantity = request.POST.get('quantity', '1')
    quantity = int(quantity) if quantity.isdigit() and int(quantity) > 0 else 1
    cart_service.add(request, part.pk, quantity)
    count = cart_service.count(request)
    message = f'« {part.name} » ajoutée au panier.'
    if _is_ajax(request):
        return JsonResponse({'status': 'success', 'message': message, 'count': count,
                             'cart_url': request.build_absolute_uri('/pieces-detachees/panier/')})
    messages.success(request, message)
    return redirect('parts:cart')


def _cart_response(request):
    """Fragment du panier (HTMX) ou page complète (sans JavaScript)."""
    if request.htmx:
        return render(request, 'parts/_cart_content.html', _cart_context(request))
    return redirect('parts:cart')


@require_POST
def cart_update(request, pk):
    quantity = request.POST.get('quantity', '')
    if quantity.lstrip('-').isdigit():
        cart_service.set_quantity(request, pk, int(quantity))
    return _cart_response(request)


@require_POST
def cart_remove(request, pk):
    cart_service.remove(request, pk)
    return _cart_response(request)


def _notify_order(order):
    """Prévient l'équipe Djona (PARTS_NOTIFY_EMAILS) et, si l'adresse est renseignée, le client.
    Ne doit jamais faire échouer la commande : elle est déjà enregistrée."""
    lines = NL.join(f'- {line.quantity} × {line.name} ({line.reference})'
                    + (f' — {line.unit_price} FCFA' if line.unit_price is not None else ' — prix sur demande')
                    for line in order.lines.all())
    recipients = getattr(settings, 'PARTS_NOTIFY_EMAILS', [])
    try:
        if recipients:
            body = NL.join([
                f'Nouvelle commande de pièces {order.reference}', '',
                f'Client : {order.full_name}' + (f' ({order.company_name})' if order.company_name else ''),
                f'Téléphone : {order.phone}', f'Email : {order.email or "—"}',
                f'Réception : {order.get_reception_display()}'
                + (f' — {order.zone_name}, {order.delivery_address}' if order.reception == PartOrder.Reception.DELIVERY else ''),
                '', lines, '',
                f'Sous-total : {order.subtotal} FCFA' + (' (+ pièces sur devis)' if order.has_unpriced_items else ''),
                f'Instructions : {order.instructions or "—"}',
            ])
            send_mail(f'Nouvelle commande de pièces {order.reference}', body, None, recipients, fail_silently=True)
        if order.email:
            body = NL.join([
                f'Bonjour {order.full_name},', '',
                f"Nous avons bien reçu votre commande {order.reference} sur Djona Parts.",
                "Elle n'est pas encore confirmée : notre équipe vérifie la disponibilité, le prix et les frais, puis vous recontacte.",
                '', lines, '', 'Vous pouvez suivre votre commande avec son numéro et votre téléphone sur djona.tech/pieces-detachees/suivi/.',
                '', 'Djona Parts',
            ])
            send_mail(f'Votre commande {order.reference} — Djona Parts', body, None, [order.email], fail_silently=True)
    except Exception:
        pass


def checkout(request):
    cart = cart_service.summary(request)
    if cart.is_empty:
        for issue in cart.issues:
            messages.warning(request, issue)
        return redirect('parts:cart')

    cache_key = f'part-order:{_client_ip(request)}'
    if request.method == 'POST':
        form = PartOrderForm(request.POST)
        attempts = cache.get(cache_key, 0)
        if attempts >= ORDER_RATE_LIMIT:
            form.add_error(None, 'Trop de commandes envoyées — réessayez plus tard.')
        elif cart.issues:
            for issue in cart.issues:
                messages.warning(request, issue)
            return redirect('parts:cart')
        elif form.is_valid():
            cache.set(cache_key, attempts + 1, ORDER_RATE_WINDOW)
            order = cart_service.create_order(form.save(commit=False), cart)
            cart_service.clear(request)
            _notify_order(order)
            request.session['part_order_reference'] = order.reference
            return redirect('parts:order_success')
    else:
        form = PartOrderForm()
    zones = list(DeliveryZone.objects.filter(is_active=True))
    return render(request, 'parts/checkout.html', {
        'form': form, 'cart': cart, 'parts_cart_count': cart.count, 'zones': zones,
        'parts_settings': PartsSettings.load(),
    })


def order_success(request):
    reference = request.session.pop('part_order_reference', None)
    if not reference:
        return redirect('parts:cart')
    order = get_object_or_404(PartOrder.objects.prefetch_related('lines'), reference=reference)
    return render(request, 'parts/order_success.html', {'order': order, 'parts_settings': PartsSettings.load()})


def track(request):
    """Suivi d'une commande par son numéro et le téléphone utilisé (pas de compte client)."""
    order, form = None, PartTrackingForm(request.POST or None)
    if request.method == 'POST':
        cache_key = f'part-track:{_client_ip(request)}'
        attempts = cache.get(cache_key, 0)
        if attempts >= TRACK_RATE_LIMIT:
            form.add_error(None, 'Trop de recherches — réessayez plus tard.')
        elif form.is_valid():
            cache.set(cache_key, attempts + 1, TRACK_RATE_WINDOW)
            candidate = PartOrder.objects.prefetch_related('lines', 'events').filter(
                reference__iexact=form.cleaned_data['reference']).first()
            if candidate and candidate.phone == form.cleaned_data['phone']:
                order = candidate
            else:
                form.add_error(None, "Aucune commande ne correspond à ce numéro et ce téléphone.")
    return render(request, 'parts/track.html', {'form': form, 'order': order})

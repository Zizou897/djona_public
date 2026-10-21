"""Panier de pièces détachées, stocké en session (comme les favoris de véhicules).

Le panier ne contient que des identifiants et des quantités : prix, disponibilité et
visibilité sont relus à chaque affichage, donc une pièce devenue indisponible, masquée
ou sans photo sort du panier avec un message.
"""
from dataclasses import dataclass, field

from django.db import transaction

from .models import Part, PartOrder, PartOrderEvent, PartOrderLine, PartsSettings

SESSION_KEY = 'parts_cart'
MAX_QUANTITY = 99


@dataclass
class CartLine:
    part: Part
    quantity: int

    @property
    def unit_price(self):
        return self.part.price

    @property
    def price_known(self):
        return self.part.price is not None

    @property
    def line_total(self):
        return self.part.price * self.quantity if self.price_known else None


@dataclass
class CartSummary:
    lines: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    @property
    def count(self):
        return sum(line.quantity for line in self.lines)

    @property
    def subtotal(self):
        return sum(line.line_total for line in self.lines if line.price_known)

    @property
    def unpriced_count(self):
        return sum(1 for line in self.lines if not line.price_known)

    @property
    def is_empty(self):
        return not self.lines


def _raw(request):
    cart = request.session.get(SESSION_KEY)
    return dict(cart) if isinstance(cart, dict) else {}


def _save(request, cart):
    request.session[SESSION_KEY] = cart
    request.session.modified = True


def count(request):
    """Nombre total d'articles (pour la pastille du menu), sans interroger la base."""
    return sum(int(q) for q in _raw(request).values() if str(q).isdigit())


def add(request, part_id, quantity=1):
    cart = _raw(request)
    key = str(part_id)
    cart[key] = min(int(cart.get(key, 0)) + max(int(quantity), 1), MAX_QUANTITY)
    _save(request, cart)


def set_quantity(request, part_id, quantity):
    cart = _raw(request)
    key = str(part_id)
    quantity = min(int(quantity), MAX_QUANTITY)
    if quantity <= 0:
        cart.pop(key, None)
    elif key in cart:
        cart[key] = quantity
    _save(request, cart)


def remove(request, part_id):
    cart = _raw(request)
    cart.pop(str(part_id), None)
    _save(request, cart)


def clear(request):
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True


def orderable(part):
    """Une pièce se commande si elle n'est pas déclarée indisponible."""
    return part.availability != Part.Availability.UNAVAILABLE


def summary(request, prune=True):
    """Lignes valides du panier. Les pièces disparues, masquées, sans photo ou indisponibles
    sont signalées dans `issues` et, avec prune=True, retirées de la session."""
    cart = _raw(request)
    ids = [int(k) for k in cart if k.isdigit()]
    parts = {p.pk: p for p in Part.objects.marketplace().select_related('category').prefetch_related('images').filter(pk__in=ids)}
    result = CartSummary()
    for key, quantity in cart.items():
        if not key.isdigit() or not str(quantity).isdigit():
            continue
        part = parts.get(int(key))
        if part is None:
            result.issues.append("Une pièce de votre panier n'est plus proposée sur le site : elle a été retirée.")
            if prune:
                cart_pop = _raw(request)
                cart_pop.pop(key, None)
                _save(request, cart_pop)
            continue
        if not orderable(part):
            result.issues.append(f'« {part.name} » est indisponible : elle a été retirée de votre panier.')
            if prune:
                cart_pop = _raw(request)
                cart_pop.pop(key, None)
                _save(request, cart_pop)
            continue
        result.lines.append(CartLine(part=part, quantity=max(int(quantity), 1)))
    result.lines.sort(key=lambda line: line.part.name)
    return result


@transaction.atomic
def create_order(order, cart_summary):
    """Enregistre la commande, ses lignes figées et le premier événement du journal.
    `order` est un PartOrder non enregistré (formulaire validé)."""
    settings_ = PartsSettings.load()
    order.subtotal = cart_summary.subtotal
    order.has_unpriced_items = cart_summary.unpriced_count > 0
    if order.reception == PartOrder.Reception.PICKUP:
        order.delivery_zone, order.zone_name, order.delivery_fee = None, '', 0
    else:
        order.zone_name = order.delivery_zone.name if order.delivery_zone else ''
        order.delivery_fee = order.delivery_zone.fee if order.delivery_zone else None
    order.commission_amount = settings_.commission_for(order.subtotal)
    order.save()
    PartOrderLine.objects.bulk_create([
        PartOrderLine(order=order, part=line.part, name=line.part.name,
                      reference=line.part.manufacturer_reference or line.part.reference,
                      unit_price=line.part.price, quantity=line.quantity)
        for line in cart_summary.lines
    ])
    PartOrderEvent.objects.create(order=order, status=order.status, note='Commande reçue')
    return order

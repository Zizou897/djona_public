from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator

from .models import Favorite, Seller, Vehicle

PAGE_SIZE = 9
MAX_COMPARE = 3

SORT_OPTIONS = {
    'recent': '-created_at',
    'price_asc': 'price',
    'price_desc': '-price',
    'mileage': 'mileage',
}


# --- Helpers session ---------------------------------------------------------

def _favorite_vehicle_ids(request):
    if not request.session.session_key:
        return set()
    return set(Favorite.objects.filter(session_key=request.session.session_key).values_list('vehicle_id', flat=True))


def _compare_ids(request):
    """Retourne la liste (ordonnée) des IDs dans le comparateur (max MAX_COMPARE)."""
    return request.session.get('compare_ids', [])


def _add_to_compare(request, vehicle_id):
    ids = _compare_ids(request)
    if vehicle_id not in ids:
        if len(ids) >= MAX_COMPARE:
            ids.pop(0)  # FIFO : retire le plus ancien
        ids.append(vehicle_id)
    request.session['compare_ids'] = ids
    request.session.modified = True
    return ids


def _remove_from_compare(request, vehicle_id):
    ids = _compare_ids(request)
    if vehicle_id in ids:
        ids.remove(vehicle_id)
    request.session['compare_ids'] = ids
    request.session.modified = True
    return ids


# --- Filtres catalogue -------------------------------------------------------

def _filtered_queryset(request):
    qs = Vehicle.objects.filter(publish=True).prefetch_related('images')

    brands = request.GET.getlist('brand')
    if brands:
        qs = qs.filter(brand__in=brands)

    transmissions = request.GET.getlist('transmission')
    if transmissions:
        qs = qs.filter(transmission__in=transmissions)

    conditions = request.GET.getlist('condition')
    if conditions:
        qs = qs.filter(condition__in=conditions)

    fuel_types = request.GET.getlist('fuel_type')
    if fuel_types:
        qs = qs.filter(fuel_type__in=fuel_types)

    city = request.GET.get('city')
    if city:
        qs = qs.filter(city=city)

    price_min = request.GET.get('price_min')
    if price_min:
        qs = qs.filter(price__gte=price_min)

    price_max = request.GET.get('price_max')
    if price_max:
        qs = qs.filter(price__lte=price_max)

    sort = request.GET.get('sort', 'recent')
    return qs.order_by(SORT_OPTIONS.get(sort, SORT_OPTIONS['recent']))


# --- Vues publiques ----------------------------------------------------------

def vehicle_list(request):
    qs = _filtered_queryset(request)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    favorite_ids = _favorite_vehicle_ids(request)
    compare_ids = _compare_ids(request)
    for vehicle in page_obj:
        vehicle.is_favorite = vehicle.id in favorite_ids
        vehicle.in_compare = vehicle.id in compare_ids

    base_qs = request.GET.copy()
    base_qs.pop('page', None)

    context = {
        'page_obj': page_obj,
        'base_qs': base_qs.urlencode(),
        'total_count': paginator.count,
        'brands': Vehicle.objects.filter(publish=True).values_list('brand', flat=True).distinct().order_by('brand'),
        'cities': Vehicle.objects.filter(publish=True).values_list('city', flat=True).distinct().order_by('city'),
        'selected_brands': request.GET.getlist('brand'),
        'selected_transmissions': request.GET.getlist('transmission'),
        'selected_conditions': request.GET.getlist('condition'),
        'selected_city': request.GET.get('city', ''),
        'price_min': request.GET.get('price_min', ''),
        'price_max': request.GET.get('price_max', ''),
        'sort': request.GET.get('sort', 'recent'),
        'compare_ids': compare_ids,
        'compare_count': len(compare_ids),
        'max_compare': MAX_COMPARE,
    }

    if request.htmx:
        return render(request, 'catalog/_results.html', context)
    return render(request, 'catalog/list.html', context)


def vehicle_detail(request, slug):
    vehicle = get_object_or_404(Vehicle.objects.prefetch_related('images'), slug=slug, publish=True)

    similar_vehicles = list(
        Vehicle.objects.filter(publish=True, brand=vehicle.brand)
        .exclude(pk=vehicle.pk)
        .prefetch_related('images')[:4]
    )
    if len(similar_vehicles) < 4:
        exclude_ids = [vehicle.pk] + [v.pk for v in similar_vehicles]
        similar_vehicles += list(
            Vehicle.objects.filter(publish=True)
            .exclude(pk__in=exclude_ids)
            .prefetch_related('images')[:4 - len(similar_vehicles)]
        )

    favorite_ids = _favorite_vehicle_ids(request)
    compare_ids = _compare_ids(request)
    vehicle.is_favorite = vehicle.id in favorite_ids
    vehicle.in_compare = vehicle.id in compare_ids
    for v in similar_vehicles:
        v.is_favorite = v.id in favorite_ids
        v.in_compare = v.id in compare_ids

    context = {
        'vehicle': vehicle,
        'similar_vehicles': similar_vehicles,
        'compare_ids': compare_ids,
        'compare_count': len(compare_ids),
        'max_compare': MAX_COMPARE,
    }
    return render(request, 'catalog/detail.html', context)


def seller_detail(request, slug):
    """Page vitrine publique d'un vendeur — catalogue publié + historique
    (annonces qu'il a eues sur le marketplace mais qui ne sont plus visibles :
    retirées, dépubliées par l'admin, ou l'annonce d'origine a changé de
    statut côté vendor). Voir apps.vendor_sync.models.Seller.
    """
    seller = get_object_or_404(Seller, slug=slug)
    published_vehicles = list(seller.vehicles.filter(publish=True).prefetch_related('images'))
    past_vehicles = list(seller.vehicles.filter(publish=False).prefetch_related('images'))

    context = {
        'seller': seller,
        'published_vehicles': published_vehicles,
        'past_vehicles': past_vehicles,
    }
    return render(request, 'catalog/seller_detail.html', context)


def vehicle_favorites(request):
    """Page dédiée des véhicules mis en favoris."""
    favorite_ids = _favorite_vehicle_ids(request)
    vehicles = list(Vehicle.objects.filter(id__in=favorite_ids, publish=True).prefetch_related('images'))
    compare_ids = _compare_ids(request)
    for vehicle in vehicles:
        vehicle.is_favorite = True
        vehicle.in_compare = vehicle.id in compare_ids

    context = {
        'vehicles': vehicles,
        'fav_count': len(vehicles),
        'compare_ids': compare_ids,
        'compare_count': len(compare_ids),
        'max_compare': MAX_COMPARE,
    }
    return render(request, 'catalog/favorites.html', context)


def vehicle_compare(request):
    """Page comparateur : affiche les vehicules en session cote a cote."""
    # POST clear : vider la selection
    if request.method == 'POST' and request.POST.get('clear'):
        request.session['compare_ids'] = []
        request.session.modified = True
        from django.shortcuts import redirect
        return redirect('catalog:compare')

    compare_ids = _compare_ids(request)
    vehicles = list(Vehicle.objects.filter(id__in=compare_ids, publish=True).prefetch_related('images'))
    # Conserver l'ordre de selection
    vehicles_map = {v.id: v for v in vehicles}
    vehicles = [vehicles_map[vid] for vid in compare_ids if vid in vehicles_map]

    # Criteres de comparaison avec tooltips
    CRITERIA = [
        {'key': 'price',        'label': 'Prix',           'icon': 'sell',              'unit': 'FCFA', 'tooltip': 'Prix affiché par le vendeur, hors frais de transaction Djona.', 'format': 'price'},
        {'key': 'year',         'label': 'Année',          'icon': 'calendar_month',    'unit': '',     'tooltip': 'Année de mise en circulation du véhicule.', 'format': 'plain'},
        {'key': 'mileage',      'label': 'Kilométrage',    'icon': 'speed',             'unit': 'km',   'tooltip': 'Kilométrage total relevé au compteur au moment de l\'annonce.', 'format': 'number'},
        {'key': 'fuel_type',    'label': 'Carburant',      'icon': 'local_gas_station', 'unit': '',     'tooltip': 'Type de carburant utilisé par le moteur.', 'format': 'choice'},
        {'key': 'transmission', 'label': 'Transmission',   'icon': 'settings',          'unit': '',     'tooltip': 'Type de boîte de vitesses (automatique ou manuelle).', 'format': 'choice'},
        {'key': 'condition',    'label': 'État',           'icon': 'new_releases',      'unit': '',     'tooltip': 'État général du véhicule : Neuf (jamais immatriculé) ou Occasion.', 'format': 'choice'},
        {'key': 'city',         'label': 'Localisation',   'icon': 'location_on',       'unit': '',     'tooltip': 'Ville où se trouve le véhicule pour la remise en main propre.', 'format': 'plain'},
        {'key': 'is_verified',  'label': 'Inspecté Djona', 'icon': 'verified',          'unit': '',     'tooltip': 'Véhicule inspecté sur 150 points de contrôle par un expert certifié Djona.', 'format': 'bool'},
    ]

    # Determiner le "Choix de l'Expert" : vehicule avec le meilleur score composite
    expert_pick_id = None
    if len(vehicles) >= 2:
        def score(v):
            s = 0
            if v.is_verified:
                s += 40
            if v.condition == 'neuf':
                s += 20
            if v.transmission == 'automatique':
                s += 10
            max_mileage = max((x.mileage for x in vehicles), default=1)
            s += int((1 - v.mileage / max_mileage) * 20)
            max_price = max((x.price for x in vehicles), default=1)
            s += int((1 - v.price / max_price) * 10)
            return s
        expert_pick_id = max(vehicles, key=score).id if vehicles else None

    context = {
        'vehicles': vehicles,
        'compare_ids': compare_ids,
        'compare_count': len(compare_ids),
        'max_compare': MAX_COMPARE,
        'criteria': CRITERIA,
        'expert_pick_id': expert_pick_id,
    }
    return render(request, 'catalog/compare.html', context)


# --- Endpoints HTMX ----------------------------------------------------------

def toggle_favorite(request, vehicle_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    vehicle = get_object_or_404(Vehicle, pk=vehicle_id, publish=True)
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key

    favorite = Favorite.objects.filter(vehicle=vehicle, session_key=session_key).first()
    if favorite:
        favorite.delete()
        is_favorite = False
    else:
        Favorite.objects.create(vehicle=vehicle, session_key=session_key)
        is_favorite = True

    if request.GET.get('from') == 'favorites' and not is_favorite:
        if request.htmx:
            return HttpResponse('')

    return render(request, 'partials/_favorite_button.html', {'vehicle': vehicle, 'is_favorite': is_favorite})


def toggle_compare(request, vehicle_id):
    """Ajoute ou retire un vehicule du comparateur (session). Reponse HTMX : bouton mis a jour."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    vehicle = get_object_or_404(Vehicle, pk=vehicle_id, publish=True)
    if not request.session.session_key:
        request.session.save()

    compare_ids = _compare_ids(request)
    if vehicle_id in compare_ids:
        compare_ids = _remove_from_compare(request, vehicle_id)
        in_compare = False
    else:
        compare_ids = _add_to_compare(request, vehicle_id)
        in_compare = True

    ctx = {
        'vehicle': vehicle,
        'in_compare': in_compare,
        'compare_count': len(compare_ids),
        'max_compare': MAX_COMPARE,
    }
    return render(request, 'partials/_compare_button.html', ctx)

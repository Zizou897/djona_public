from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator

from .models import Favorite, Vehicle

PAGE_SIZE = 9

SORT_OPTIONS = {
    'recent': '-created_at',
    'price_asc': 'price',
    'price_desc': '-price',
    'mileage': 'mileage',
}


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


def vehicle_list(request):
    qs = _filtered_queryset(request)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    favorite_ids = _favorite_vehicle_ids(request)
    for vehicle in page_obj:
        vehicle.is_favorite = vehicle.id in favorite_ids

    context = {
        'page_obj': page_obj,
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
    vehicle.is_favorite = vehicle.id in favorite_ids
    for v in similar_vehicles:
        v.is_favorite = v.id in favorite_ids

    context = {
        'vehicle': vehicle,
        'similar_vehicles': similar_vehicles,
    }
    return render(request, 'catalog/detail.html', context)


def _favorite_vehicle_ids(request):
    if not request.session.session_key:
        return set()
    return set(Favorite.objects.filter(session_key=request.session.session_key).values_list('vehicle_id', flat=True))


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

    return render(request, 'partials/_favorite_button.html', {'vehicle': vehicle, 'is_favorite': is_favorite})

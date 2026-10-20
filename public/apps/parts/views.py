from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat, Replace, Upper
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.catalog.models import Vehicle
from apps.core.views import _client_ip

from .forms import PartRequestForm
from .models import Part, PartCategory, PartCompatibility, PartRequest, normalize_reference

PAGE_SIZE = 12
REQUEST_RATE_LIMIT = 5
REQUEST_RATE_WINDOW = 3600  # secondes (1 h)
NL = chr(10)
SORTS = {
    'pertinence': ('-is_featured', 'name'),
    'prix_asc': ('price', 'name'),
    'prix_desc': ('-price', 'name'),
}


def _active_parts():
    return Part.objects.filter(is_active=True, category__is_active=True).select_related('category').prefetch_related('images')


def _unique_casefold(values):
    seen, out = set(), []
    for value in values:
        key = value.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out


def _known_makes():
    """Marques pour lesquelles au moins une pièce visible a une compatibilité."""
    values = (PartCompatibility.objects.filter(part__is_active=True, part__category__is_active=True)
              .order_by('make').values_list('make', flat=True).distinct())
    return sorted(_unique_casefold(values), key=str.casefold)


def _models_for(make):
    if not make:
        return []
    values = (PartCompatibility.objects.filter(part__is_active=True, part__category__is_active=True, make__iexact=make)
              .exclude(model='').order_by('model').values_list('model', flat=True).distinct())
    return sorted(_unique_casefold(values), key=str.casefold)


def _vehicle_from(params):
    make = params.get('marque', '').strip()[:60]
    model = params.get('modele', '').strip()[:80]
    year = params.get('annee', '').strip()
    year = int(year) if year.isdigit() and 1950 <= int(year) <= 2100 else None
    return {'make': make, 'model': model, 'year': year}


def _compatibility_filter(vehicle):
    qs = PartCompatibility.objects.filter(make__iexact=vehicle['make'])
    if vehicle['model']:
        qs = qs.filter(Q(model='') | Q(model__iexact=vehicle['model']))
    if vehicle['year']:
        year = vehicle['year']
        qs = qs.filter(Q(year_from__isnull=True) | Q(year_from__lte=year),
                       Q(year_to__isnull=True) | Q(year_to__gte=year))
    return qs


def _search(params):
    qs = _active_parts()
    query = params.get('q', '').strip()[:100]
    tokens = query.split()
    use_ref = any(len(normalize_reference(t)) >= 3 for t in tokens)
    if use_ref:
        qs = qs.annotate(ref_norm=_ref_norm_expr())
    for token in tokens:
        cond = (Q(name__icontains=token) | Q(brand__icontains=token) | Q(description__icontains=token)
                | Q(reference__icontains=token) | Q(manufacturer_reference__icontains=token))
        norm = normalize_reference(token)
        if len(norm) >= 3:
            cond |= Q(ref_norm__contains=norm)
        qs = qs.filter(cond)

    category = params.get('categorie', '')
    if category.isdigit():
        qs = qs.filter(category_id=int(category))

    vehicle = _vehicle_from(params)
    if vehicle['make']:
        qs = qs.filter(pk__in=_compatibility_filter(vehicle).values('part_id'))

    budget = params.get('budget', '').strip()
    if budget.isdigit():
        qs = qs.filter(price__lte=int(budget))

    sort = params.get('tri', 'pertinence')
    qs = qs.order_by(*SORTS.get(sort, SORTS['pertinence']))
    return qs, {'q': query, 'categorie': category, 'budget': budget, 'tri': sort if sort in SORTS else 'pertinence', **vehicle}


def _ref_norm_expr():
    expr = Upper(Concat('reference', Value(' '), 'manufacturer_reference'))
    for char in ('-', ' ', '.', '/', '_'):
        expr = Replace(expr, Value(char), Value(''))
    return expr


def _vehicle_context(vehicle):
    return {
        'makes': _known_makes(),
        'models': _models_for(vehicle['make']),
        'vehicle': vehicle,
    }


def home(request):
    vehicle = _vehicle_from(request.GET)
    parts = _active_parts()
    categories = PartCategory.objects.filter(is_active=True)
    context = {
        'categories': categories,
        'featured': list(parts.filter(is_featured=True)[:8]),
        'has_catalog': parts.exists(),
        **_vehicle_context(vehicle),
    }
    return render(request, 'parts/home.html', context)


def search(request):
    params = request.GET.copy()
    # Changer de marque dans les filtres renvoie l'ancien modèle : on l'ignore s'il
    # n'existe pas pour la marque choisie (sinon résultats vides le temps du rafraîchissement).
    make, model = params.get('marque', '').strip(), params.get('modele', '').strip()
    if make and model and model.casefold() not in {m.casefold() for m in _models_for(make)}:
        params['modele'] = ''
    qs, filters = _search(params)
    page = Paginator(qs, PAGE_SIZE).get_page(params.get('page'))
    params.pop('page', None)
    categories = PartCategory.objects.filter(is_active=True)
    category = next((c for c in categories if str(c.pk) == filters['categorie']), None)
    context = {
        'page_obj': page,
        'filters': filters,
        'querystring': params.urlencode(),
        'categories': categories,
        'category': category,
        'has_vehicle': bool(filters['make']),
        **_vehicle_context({k: filters[k] for k in ('make', 'model', 'year')}),
    }
    if request.htmx:
        return render(request, 'parts/_results.html', context)
    return render(request, 'parts/search.html', context)


def models_options(request):
    """Liste déroulante des modèles d'une marque (requête HTMX du sélecteur)."""
    vehicle = _vehicle_from(request.GET)
    return render(request, 'parts/_model_options.html', {'models': _models_for(vehicle['make']), 'vehicle': vehicle})


def detail(request, pk, slug):
    part = get_object_or_404(_active_parts(), pk=pk)
    if slug != part.slug:
        return redirect(part.get_absolute_url(), permanent=True)
    vehicle = _vehicle_from(request.GET)
    compatibility = None
    if vehicle['make']:
        matches = _compatibility_filter(vehicle).filter(part=part).exists()
        compatibility = 'compatible' if matches else 'unknown'
    related = (_active_parts().filter(category=part.category).exclude(pk=part.pk)[:4])
    whatsapp_message = f'Bonjour, je souhaite la pièce « {part.name} » (réf. {part.reference})'
    if vehicle['make']:
        whatsapp_message += f" pour ma {vehicle['make']} {vehicle['model']} {vehicle['year'] or ''}".rstrip()
    whatsapp_message += '.' + chr(10) + request.build_absolute_uri()
    return render(request, 'parts/detail.html', {
        'whatsapp_message': whatsapp_message,
        'part': part,
        'images': list(part.images.all()),
        'compatibilities': list(part.compatibilities.all()),
        'compatibility': compatibility,
        'vehicle': vehicle,
        'related': related,
    })


def _notify_part_request(part_request):
    """Notifie l'équipe Djona par email (settings.PARTS_NOTIFY_EMAILS ; sans
    effet si vide). Ne doit jamais faire échouer la soumission : la demande est
    déjà enregistrée et visible dans le back-office."""
    recipients = getattr(settings, 'PARTS_NOTIFY_EMAILS', [])
    if not recipients:
        return
    body = NL.join([
        f'Nouvelle demande de pièce {part_request.reference}',
        '',
        f'Client : {part_request.full_name}',
        f'Téléphone : {part_request.phone}',
        f'Véhicule : {part_request.make} {part_request.model} {part_request.year}'
        + (f' — {part_request.engine}' if part_request.engine else ''),
        f'Pièce : {part_request.part_name}' + (f' (réf. {part_request.part_reference})' if part_request.part_reference else ''),
        '',
        f'Description : {part_request.description}',
    ])
    try:
        send_mail(f'Nouvelle demande de pièce {part_request.reference}', body, None, recipients, fail_silently=True)
    except Exception:
        pass


def request_part(request):
    part = None
    part_id = request.GET.get('piece') or request.POST.get('piece')
    if part_id and part_id.isdigit():
        part = _active_parts().filter(pk=int(part_id)).first()

    if request.method == 'POST':
        cache_key = f'part-request:{_client_ip(request)}'
        attempts = cache.get(cache_key, 0)
        form = PartRequestForm(request.POST, request.FILES)
        if attempts >= REQUEST_RATE_LIMIT:
            form.add_error(None, 'Trop de demandes envoyées — réessayez plus tard.')
        elif form.is_valid():
            cache.set(cache_key, attempts + 1, REQUEST_RATE_WINDOW)
            part_request = form.save(commit=False)
            part_request.part = part
            part_request.save()
            _notify_part_request(part_request)
            request.session['part_request_reference'] = part_request.reference
            return redirect('parts:request_success')
    else:
        vehicle = _vehicle_from(request.GET)
        initial = {
            'make': vehicle['make'], 'model': vehicle['model'], 'year': vehicle['year'],
            'part_name': request.GET.get('piece_nom', '').strip()[:150],
        }
        if part:
            initial.update(part_name=part.name, part_reference=part.manufacturer_reference or part.reference)
        form = PartRequestForm(initial=initial)
    return render(request, 'parts/request_form.html', {
        'form': form, 'part': part, 'makes': _known_makes(),
        'catalog_makes': _unique_casefold(Vehicle.objects.order_by('brand').values_list('brand', flat=True).distinct()),
    })


def request_success(request):
    reference = request.session.pop('part_request_reference', None)
    if not reference:
        return redirect('parts:request')
    return render(request, 'parts/request_success.html', {'reference': reference, 'today': timezone.localdate()})

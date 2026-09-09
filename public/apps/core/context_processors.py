from .models import Partner


def active_partners(request):
    """Rend les partenaires actifs disponibles dans tous les templates — seuls
    home.html, catalog/list.html et catalog/detail.html affichent le bandeau.
    """
    return {'active_partners': Partner.objects.filter(publish=True)}

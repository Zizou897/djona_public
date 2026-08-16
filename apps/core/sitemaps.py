from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Vehicle


class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'

    def items(self):
        return ['core:home', 'catalog:list', 'core:contact', 'core:privacy', 'core:terms', 'core:seller_terms']

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item in ('core:home', 'catalog:list') else 0.4


class VehicleSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Vehicle.objects.filter(publish=True)

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.updated_at

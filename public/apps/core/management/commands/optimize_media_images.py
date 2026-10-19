"""Convertit en WebP les images déjà enregistrées (photos de véhicules, logos
vendeurs et partenaires, photos de pièces).

Les nouveaux téléversements sont convertis à l'enregistrement ; cette commande
rattrape l'existant. Idempotente : un fichier déjà en WebP, animé ou qui
deviendrait plus lourd est laissé tel quel.

    python manage.py optimize_media_images --dry-run
    python manage.py optimize_media_images
"""
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Seller, VehicleImage
from apps.core.imaging import SMALL_MAX_WIDTH, SMALL_QUALITY, VEHICLE_MAX_WIDTH, VEHICLE_QUALITY, convert_path
from apps.core.models import Partner
from apps.parts.models import PartImage


def human(size):
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if size < 1024 or unit == 'Go':
            return f'{size:.0f} {unit}' if unit == 'o' else f'{size:.1f} {unit}'
        size /= 1024


class Command(BaseCommand):
    help = 'Convertit en WebP les images existantes (véhicules, logos, pièces).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='simule sans rien modifier')

    def handle(self, *args, dry_run=False, **options):
        targets = [
            ('Photos de véhicules', VehicleImage.objects.all(), 'image', VEHICLE_MAX_WIDTH, VEHICLE_QUALITY),
            ('Photos de pièces', PartImage.objects.all(), 'image', VEHICLE_MAX_WIDTH, VEHICLE_QUALITY),
            ('Logos vendeurs', Seller.objects.exclude(logo='').exclude(logo__isnull=True), 'logo', SMALL_MAX_WIDTH, SMALL_QUALITY),
            ('Logos partenaires', Partner.objects.all(), 'logo', SMALL_MAX_WIDTH, SMALL_QUALITY),
        ]
        total_before = total_after = 0
        for label, queryset, field, max_width, quality in targets:
            converted = kept = missing = 0
            for obj in queryset:
                name = getattr(obj, field).name
                source = Path(settings.MEDIA_ROOT) / name
                if not name or source.suffix.lower() == '.webp':
                    continue
                if not source.exists():
                    missing += 1
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    result = convert_path(source, tmp, max_width=max_width, quality=quality)
                    if result.suffix.lower() != '.webp':
                        kept += 1
                        continue
                    before, after = source.stat().st_size, result.stat().st_size
                    total_before += before
                    total_after += after
                    converted += 1
                    if dry_run:
                        continue
                    destination = source.with_suffix('.webp')
                    destination.write_bytes(result.read_bytes())
                setattr(obj, field, str(Path(name).with_suffix('.webp')).replace('\\', '/'))
                obj.save(update_fields=[field])
                source.unlink(missing_ok=True)
            self.stdout.write(f'{label} : {converted} converti(s), {kept} conservé(s) tel(s) quel(s)'
                              + (f', {missing} fichier(s) introuvable(s)' if missing else ''))
        prefix = 'Simulation : ' if dry_run else ''
        if total_before:
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}{human(total_before)} -> {human(total_after)} (gain {human(total_before - total_after)}).'))
        else:
            self.stdout.write('Rien à convertir.')

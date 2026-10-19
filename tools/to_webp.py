#!/usr/bin/env python3
"""Convertit des images (JPG, PNG, BMP, TIFF, GIF non animé) en WebP.

Exemples :
    python tools/to_webp.py photo.jpg                      # -> photo.webp à côté
    python tools/to_webp.py public/static/img -r           # dossier, récursif
    python tools/to_webp.py images/ -o webp/ -q 75         # dossier de sortie, qualité 75
    python tools/to_webp.py images/ -r --max-width 1600    # réduit les images trop larges
    python tools/to_webp.py logos/ --lossless              # sans perte (logos, captures)
    python tools/to_webp.py images/ -r --dry-run           # simule, n'écrit rien
    python tools/to_webp.py images/ -r --delete-originals  # supprime l'original converti

Par défaut : qualité 80, les .webp existants ne sont pas écrasés (--overwrite pour
forcer) et un fichier WebP plus lourd que l'original est ignoré (--keep-larger pour
le garder quand même). Seule dépendance : Pillow.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

SOURCE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.gif'}
DEFAULT_QUALITY = 80


class Result:
    CONVERTED = 'converti'
    SKIPPED_EXISTS = 'déjà converti'
    SKIPPED_LARGER = 'webp plus lourd'
    SKIPPED_ANIMATED = 'animé'
    FAILED = 'échec'


def find_images(source, recursive):
    """Fichiers images à convertir sous `source` (fichier ou dossier)."""
    source = Path(source)
    if source.is_file():
        return [source] if source.suffix.lower() in SOURCE_EXTENSIONS else []
    pattern = '**/*' if recursive else '*'
    return sorted(p for p in source.glob(pattern) if p.is_file() and p.suffix.lower() in SOURCE_EXTENSIONS)


def destination_for(path, source, output):
    """Chemin du .webp : à côté de l'original, ou sous `output` en gardant l'arborescence."""
    if output is None:
        return path.with_suffix('.webp')
    base = Path(source) if Path(source).is_dir() else Path(source).parent
    return (Path(output) / path.relative_to(base)).with_suffix('.webp')


def convert_image(path, destination, quality=DEFAULT_QUALITY, lossless=False, max_width=None,
                  overwrite=False, keep_larger=False, dry_run=False):
    """Convertit une image. Retourne (statut, taille_originale, taille_webp)."""
    original_size = path.stat().st_size
    if destination.exists() and not overwrite:
        return Result.SKIPPED_EXISTS, original_size, destination.stat().st_size
    try:
        with Image.open(path) as image:
            if getattr(image, 'is_animated', False):
                return Result.SKIPPED_ANIMATED, original_size, 0
            image = ImageOps.exif_transpose(image)  # respecte l'orientation des photos de téléphone
            if max_width and image.width > max_width:
                height = round(image.height * max_width / image.width)
                image = image.resize((max_width, height), Image.LANCZOS)
            has_alpha = image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info)
            image = image.convert('RGBA' if has_alpha else 'RGB')
            options = {'lossless': True} if lossless else {'quality': quality}
            options['method'] = 6  # compression la plus poussée, un peu plus lente
            if dry_run:
                import io
                buffer = io.BytesIO()
                image.save(buffer, 'WEBP', **options)
                webp_size = buffer.tell()
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(destination.name + '.tmp')
                image.save(temporary, 'WEBP', **options)
                webp_size = temporary.stat().st_size
    except (UnidentifiedImageError, OSError, ValueError):
        return Result.FAILED, original_size, 0

    if webp_size >= original_size and not keep_larger:
        if not dry_run:
            temporary.unlink(missing_ok=True)
        return Result.SKIPPED_LARGER, original_size, webp_size
    if not dry_run:
        temporary.replace(destination)
    return Result.CONVERTED, original_size, webp_size


def human(size):
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if size < 1024 or unit == 'Go':
            return f'{size:.0f} {unit}' if unit == 'o' else f'{size:.1f} {unit}'
        size /= 1024


def build_parser():
    parser = argparse.ArgumentParser(description='Convertit des images en WebP.')
    parser.add_argument('source', help='fichier image ou dossier')
    parser.add_argument('-o', '--output', help='dossier de sortie (défaut : à côté des originaux)')
    parser.add_argument('-r', '--recursive', action='store_true', help='parcourt les sous-dossiers')
    parser.add_argument('-q', '--quality', type=int, default=DEFAULT_QUALITY, help=f'qualité 1-100 (défaut {DEFAULT_QUALITY})')
    parser.add_argument('--lossless', action='store_true', help='compression sans perte')
    parser.add_argument('--max-width', type=int, help='réduit les images plus larges (px)')
    parser.add_argument('--overwrite', action='store_true', help='écrase les .webp existants')
    parser.add_argument('--keep-larger', action='store_true', help='garde le .webp même s\'il est plus lourd')
    parser.add_argument('--delete-originals', action='store_true', help='supprime chaque original converti')
    parser.add_argument('--dry-run', action='store_true', help='simule sans rien écrire ni supprimer')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not 1 <= args.quality <= 100:
        print('Erreur : la qualité doit être comprise entre 1 et 100.', file=sys.stderr)
        return 2
    source = Path(args.source)
    if not source.exists():
        print(f'Erreur : {source} introuvable.', file=sys.stderr)
        return 2

    images = find_images(source, args.recursive)
    if not images:
        print('Aucune image à convertir.' + ('' if args.recursive or source.is_file() else ' (essayez -r pour les sous-dossiers)'))
        return 0

    total_before = total_after = 0
    counts = {}
    for path in images:
        destination = destination_for(path, source, args.output)
        status, before, after = convert_image(
            path, destination, quality=args.quality, lossless=args.lossless, max_width=args.max_width,
            overwrite=args.overwrite, keep_larger=args.keep_larger, dry_run=args.dry_run,
        )
        counts[status] = counts.get(status, 0) + 1
        if status == Result.CONVERTED:
            total_before += before
            total_after += after
            saving = 100 - after * 100 / before if before else 0
            print(f'  {path} -> {destination.name}  {human(before)} -> {human(after)} (-{saving:.0f} %)')
            if args.delete_originals and not args.dry_run:
                path.unlink()
        else:
            print(f'  {path}  [{status}]')

    prefix = 'Simulation : ' if args.dry_run else ''
    summary = ', '.join(f'{n} {status}' for status, n in counts.items())
    print(f'\n{prefix}{summary}.')
    if total_before:
        print(f'{prefix}{human(total_before)} -> {human(total_after)} (gain {human(total_before - total_after)}, -{100 - total_after * 100 / total_before:.0f} %).')
    return 1 if counts.get(Result.FAILED) else 0


if __name__ == '__main__':
    sys.exit(main())

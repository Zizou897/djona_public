"""Conversion des images téléversées en WebP.

Ce fichier existe en trois copies identiques (public/apps/core/imaging.py,
vendor/core/src/app/imaging.py, admin/core/src/app/imaging.py) car les trois
projets Django sont indépendants ; un test (tools/test_imaging_sync.py) vérifie
qu'elles restent identiques — modifiez-les ensemble.
"""
import io
import os
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

VEHICLE_MAX_WIDTH = 1600
VEHICLE_QUALITY = 82
SMALL_MAX_WIDTH = 600  # logos, avatars
SMALL_QUALITY = 88

_ERRORS = (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError)


def _encode(image, max_width, quality):
    """Image PIL ouverte -> octets WebP (orientation EXIF appliquée, largeur plafonnée)."""
    image = ImageOps.exif_transpose(image)
    if max_width and image.width > max_width:
        height = round(image.height * max_width / image.width)
        image = image.resize((max_width, height), Image.LANCZOS)
    has_alpha = image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info)
    image = image.convert('RGBA' if has_alpha else 'RGB')
    buffer = io.BytesIO()
    image.save(buffer, 'WEBP', quality=quality, method=4)
    return buffer.getvalue()


FALLBACK_QUALITIES = (72, 62)


def _encode_within(image, max_width, quality, limit):
    """Encode en WebP ; si le résultat n'est pas plus léger que `limit` (taille de
    l'original), retente à qualité plus basse — un JPEG déjà très compressé reste
    ainsi convertible plutôt que de rester en JPEG."""
    data = _encode(image, max_width, quality)
    for fallback in FALLBACK_QUALITIES:
        if len(data) < limit or fallback >= quality:
            break
        data = _encode(image, max_width, fallback)
    return data


def optimize_upload(upload, max_width=VEHICLE_MAX_WIDTH, quality=VEHICLE_QUALITY, name=None):
    """Retourne un fichier WebP (ContentFile nommé *.webp) à partir d'un fichier
    téléversé, ou `upload` inchangé s'il ne faut/peut pas le convertir : image
    illisible (la validation du formulaire s'en charge), GIF animé, WebP déjà
    assez petit, ou conversion qui alourdirait le fichier."""
    try:
        upload.seek(0)
        raw = upload.read()
        upload.seek(0)
        with Image.open(io.BytesIO(raw)) as image:
            if getattr(image, 'is_animated', False):
                return upload
            if image.format == 'WEBP' and image.width <= (max_width or image.width):
                return upload
            data = _encode_within(image, max_width, quality, len(raw))
    except _ERRORS:
        return upload
    if len(data) >= len(raw):
        return upload
    stem = Path(os.path.basename(name or getattr(upload, 'name', '') or 'image')).stem or 'image'
    return ContentFile(data, name=f'{stem}.webp')


def optimize_field(fieldfile, **kwargs):
    """À appeler dans save() avec un FieldFile : ne touche qu'une image tout juste
    téléversée (pas encore enregistrée) ; retourne le fichier à affecter au champ."""
    if not fieldfile or getattr(fieldfile, '_committed', True):
        return fieldfile
    return optimize_upload(fieldfile.file, name=fieldfile.name, **kwargs)


def convert_path(source, destination_dir, max_width=VEHICLE_MAX_WIDTH, quality=VEHICLE_QUALITY):
    """Convertit un fichier du disque en WebP dans `destination_dir` (créé au
    besoin) et retourne le chemin écrit : `<nom>.webp`, ou une copie de l'original
    sous son propre nom s'il est illisible, animé ou si le WebP serait plus lourd."""
    import shutil
    source, destination_dir = Path(source), Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source) as image:
            if getattr(image, 'is_animated', False):
                raise ValueError('animé')
            data = _encode_within(image, max_width, quality, source.stat().st_size)
    except _ERRORS:
        data = None
    if data is not None and (len(data) < source.stat().st_size or source.suffix.lower() == '.webp'):
        target = destination_dir / f'{source.stem}.webp'
        target.write_bytes(data)
        return target
    target = destination_dir / source.name
    shutil.copyfile(source, target)
    return target

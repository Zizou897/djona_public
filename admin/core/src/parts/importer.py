"""Lecture des compatibilités et import CSV du catalogue Djona Parts.

Format d'un véhicule compatible : « Marque / Modèle / Année début / Année fin /
Motorisation » (seule la marque est obligatoire). Dans le fichier CSV, plusieurs
véhicules sont séparés par « | » ; dans le formulaire, un véhicule par ligne.
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import transaction

from .models import PartCategoryMirror, PartCompatibilityMirror, PartMirror

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
YEAR_MIN, YEAR_MAX = 1950, 2100

COLUMNS = [
    ('reference', 'Référence Djona (obligatoire, unique)'),
    ('designation', 'Désignation (obligatoire)'),
    ('categorie', 'Catégorie (obligatoire, nom exact d\'une catégorie existante)'),
    ('marque_piece', 'Marque de la pièce'),
    ('reference_fabricant', 'Référence fabricant / OEM'),
    ('etat', 'neuf, reconditionné ou occasion (vide = non précisé)'),
    ('prix', 'Prix en FCFA (vide = prix sur demande)'),
    ('disponibilite', 'disponible, indisponible ou à confirmer (vide = à confirmer)'),
    ('garantie', 'Garantie'),
    ('delai', 'Délai estimé'),
    ('description', 'Description'),
    ('compatibilites', 'Véhicules compatibles : Marque/Modèle/Début/Fin/Motorisation séparés par |'),
    ('visible', 'oui ou non (vide = oui)'),
    ('populaire', 'oui ou non (vide = non)'),
]
REQUIRED = ('reference', 'designation', 'categorie')
ALIASES = {
    'reference_djona': 'reference', 'ref': 'reference', 'nom': 'designation', 'categories': 'categorie',
    'marque': 'marque_piece', 'reference_oem': 'reference_fabricant', 'oem': 'reference_fabricant',
    'prix_fcfa': 'prix', 'etat_de_la_piece': 'etat', 'delai_estime': 'delai',
    'vehicules_compatibles': 'compatibilites', 'compatibilite': 'compatibilites',
}

CONDITIONS = {'neuf': 'neuf', 'reconditionne': 'reconditionne', 'occasion': 'occasion'}
AVAILABILITIES = {
    'disponible': 'disponible', 'indisponible': 'indisponible',
    'a confirmer': 'a_confirmer', 'a_confirmer': 'a_confirmer', 'aconfirmer': 'a_confirmer',
}
YES = {'oui', 'o', 'yes', 'y', '1', 'true', 'vrai', 'x'}
NO = {'non', 'n', 'no', '0', 'false', 'faux'}


def fold(value):
    """Minuscules sans accents ni espaces superflus."""
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text.strip().lower())


def parse_compatibility(text):
    """Une ligne « Marque / Modèle / Début / Fin / Motorisation » → dict.
    Lève ValueError avec un message lisible."""
    parts = [p.strip() for p in text.split('/')]
    parts += [''] * (5 - len(parts))
    if len(parts) > 5:
        raise ValueError(f'« {text} » : 5 éléments au maximum (marque/modèle/début/fin/motorisation).')
    make, model, start, end, engine = parts[:5]
    if not make:
        raise ValueError(f'« {text} » : la marque est obligatoire.')
    years = []
    for label, raw in (('début', start), ('fin', end)):
        if not raw:
            years.append(None)
            continue
        if not raw.isdigit() or not YEAR_MIN <= int(raw) <= YEAR_MAX:
            raise ValueError(f'« {text} » : année de {label} invalide ({raw}).')
        years.append(int(raw))
    if years[0] and years[1] and years[0] > years[1]:
        raise ValueError(f'« {text} » : l\'année de début dépasse l\'année de fin.')
    return {'make': make[:60], 'model': model[:80], 'year_from': years[0], 'year_to': years[1], 'engine': engine[:80]}


def parse_compatibilities(raw, separator='\n'):
    items = [chunk.strip() for chunk in re.split(r'\r?\n' if separator == '\n' else re.escape(separator), raw or '') if chunk.strip()]
    return [parse_compatibility(item) for item in items]


def format_compatibilities(rows):
    lines = []
    for row in rows:
        lines.append(' / '.join([
            row.make, row.model, str(row.year_from or ''), str(row.year_to or ''), row.engine,
        ]).rstrip(' /'))
    return '\n'.join(lines)


def replace_compatibilities(part, items):
    PartCompatibilityMirror.objects.using('public_db').filter(part=part).delete()
    PartCompatibilityMirror.objects.using('public_db').bulk_create(
        [PartCompatibilityMirror(part=part, **item) for item in items])


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    errors: list = field(default_factory=list)  # [(ligne, message)]
    ignored_columns: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors


def _decode(raw):
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('Encodage du fichier non reconnu (utilisez UTF-8).')


def _parse_price(raw):
    value = re.sub(r'(?i)\s*(fcfa|xof|cfa|f)\s*$', '', raw.strip())
    value = re.sub(r'[\s  ]', '', value)
    if re.fullmatch(r'\d{1,3}(\.\d{3})+', value):
        value = value.replace('.', '')
    if not value.isdigit():
        raise ValueError(f'prix invalide « {raw} » (chiffres uniquement, en FCFA).')
    return int(value)


def _parse_bool(raw, default, label):
    key = fold(raw)
    if not key:
        return default
    if key in YES:
        return True
    if key in NO:
        return False
    raise ValueError(f'« {raw} » n\'est pas une valeur valide pour « {label} » (oui ou non).')


def _clean_row(row, categories):
    reference = row['reference'].strip()
    name = row['designation'].strip()
    if not reference:
        raise ValueError('référence manquante.')
    if len(reference) > 60:
        raise ValueError('référence trop longue (60 caractères maximum).')
    if not name:
        raise ValueError('désignation manquante.')
    category = categories.get(fold(row['categorie']))
    if not category:
        raise ValueError(f'catégorie inconnue « {row["categorie"]} » — choisissez parmi : {", ".join(c.name for c in categories.values())}.')

    condition = ''
    if fold(row['etat']):
        condition = CONDITIONS.get(fold(row['etat']))
        if condition is None:
            raise ValueError(f'état « {row["etat"]} » inconnu (neuf, reconditionné ou occasion).')
    availability = 'a_confirmer'
    if fold(row['disponibilite']):
        availability = AVAILABILITIES.get(fold(row['disponibilite']))
        if availability is None:
            raise ValueError(f'disponibilité « {row["disponibilite"]} » inconnue (disponible, indisponible ou à confirmer).')
    price = _parse_price(row['prix']) if row['prix'].strip() else None
    compat = parse_compatibilities(row['compatibilites'], separator='|')
    return {
        'reference': reference,
        'defaults': {
            'name': name[:150],
            'category': category,
            'brand': row['marque_piece'].strip()[:80],
            'manufacturer_reference': row['reference_fabricant'].strip()[:80],
            'condition': condition,
            'price': price,
            'availability': availability,
            'warranty': row['garantie'].strip()[:150],
            'lead_time': row['delai'].strip()[:100],
            'description': row['description'].strip(),
            'is_active': _parse_bool(row['visible'], True, 'visible'),
            'is_featured': _parse_bool(row['populaire'], False, 'populaire'),
        },
        'compat': compat,
    }


def import_parts(raw_bytes):
    """Importe un fichier CSV. Tout ou rien : s'il y a une seule erreur, rien
    n'est écrit et le rapport liste les lignes à corriger."""
    report = ImportReport()
    if len(raw_bytes) > MAX_BYTES:
        report.errors.append((0, 'Fichier trop volumineux (2 Mo maximum).'))
        return report
    try:
        text = _decode(raw_bytes)
    except ValueError as exc:
        report.errors.append((0, str(exc)))
        return report

    sample = text[:2000].splitlines()[0] if text.strip() else ''
    delimiter = max(';,\t', key=sample.count) if sample else ';'
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        report.errors.append((0, 'Le fichier est vide.'))
        return report

    known = {name for name, _ in COLUMNS}
    index = {}
    for position, raw in enumerate(header):
        key = re.sub(r'[^a-z]+', '_', fold(raw)).strip('_')
        key = ALIASES.get(key, key)
        if key in known and key not in index:
            index[key] = position
        elif raw.strip():
            report.ignored_columns.append(raw.strip())
    missing = [c for c in REQUIRED if c not in index]
    if missing:
        report.errors.append((1, f'Colonnes obligatoires manquantes : {", ".join(missing)}.'))
        return report

    categories = {fold(c.name): c for c in PartCategoryMirror.objects.using('public_db').all()}
    seen, prepared = {}, []
    for line_no, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(prepared) + len(report.errors) >= MAX_ROWS:
            report.errors.append((line_no, f'Plus de {MAX_ROWS} lignes : découpez le fichier.'))
            break
        row = {name: (cells[index[name]] if name in index and index[name] < len(cells) else '') for name, _ in COLUMNS}
        try:
            data = _clean_row(row, categories)
        except ValueError as exc:
            report.errors.append((line_no, str(exc)))
            continue
        key = data['reference'].casefold()
        if key in seen:
            report.errors.append((line_no, f'référence « {data["reference"]} » déjà présente à la ligne {seen[key]}.'))
            continue
        seen[key] = line_no
        data['line'] = line_no
        prepared.append(data)

    if report.errors:
        return report
    if not prepared:
        report.errors.append((0, 'Aucune ligne à importer.'))
        return report

    with transaction.atomic(using='public_db'):
        for data in prepared:
            part = PartMirror.objects.using('public_db').filter(reference__iexact=data['reference']).first()
            if part:
                for attr, value in data['defaults'].items():
                    setattr(part, attr, value)
                part.save(using='public_db')
                report.updated += 1
            else:
                part = PartMirror(reference=data['reference'], **data['defaults'])
                part.save(using='public_db')
                report.created += 1
            if data['compat']:
                replace_compatibilities(part, data['compat'])
    return report


def sample_csv():
    """Modèle téléchargeable : en-têtes + deux lignes d'exemple (séparateur « ; »,
    encodage UTF-8 avec BOM pour Excel)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';', lineterminator='\r\n')
    writer.writerow([name for name, _ in COLUMNS])
    writer.writerow(['DJP-0001', 'Plaquettes de frein avant', 'Freinage', 'Bosch', '04465-33450', 'neuf',
                     '25000', 'à confirmer', '6 mois', '', 'Jeu de 4 plaquettes.',
                     'Toyota/Corolla/2014/2019|Toyota/Yaris/2012/2018', 'oui', 'non'])
    writer.writerow(['DJP-0002', 'Filtre à huile', 'Filtration', '', '90915-YZZE1', '', '', '', '', '', '',
                     'Toyota', 'oui', 'non'])
    return '﻿' + out.getvalue()

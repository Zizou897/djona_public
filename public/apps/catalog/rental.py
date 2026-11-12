"""Durée d'une location : calcul des jours et catégorie (courte / moyenne / longue durée).

Source unique des seuils : le serveur (validation, admin) et la fiche véhicule (JavaScript,
via `RENTAL_CATEGORIES` sérialisé dans la page) lisent tous deux cette liste.
"""
from datetime import date

# Jours inclus dans chaque catégorie. `max_days=None` : sans limite haute.
RENTAL_CATEGORIES = [
    {'key': 'courte', 'label': 'Courte durée', 'min_days': 1, 'max_days': 7, 'range': '1 à 7 jours'},
    {'key': 'moyenne', 'label': 'Moyenne durée', 'min_days': 8, 'max_days': 29, 'range': '8 à 29 jours'},
    {'key': 'longue', 'label': 'Longue durée', 'min_days': 30, 'max_days': None, 'range': '30 jours et plus'},
]


def rental_days(start: date, end: date) -> int:
    """Nombre de jours de location : du jour de début au jour de retour (retour exclu)."""
    return (end - start).days


def duration_category(days: int):
    """Catégorie correspondant à `days` (≥ 1), ou None si la durée n'est pas valide."""
    for category in RENTAL_CATEGORIES:
        if days >= category['min_days'] and (category['max_days'] is None or days <= category['max_days']):
            return category
    return None

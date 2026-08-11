from django.shortcuts import render

FEATURED_VEHICLES = [
    {
        'name': 'Toyota Land Cruiser 300',
        'price': '85M FCFA',
        'location': 'Cocody, Abidjan',
        'year': 2023,
        'mileage': '12 500 km',
        'transmission': 'Auto',
        'image': 'img/vehicles/toyota-land-cruiser-300.svg',
        'is_verified': True,
        'condition': 'Occasion',
    },
    {
        'name': 'Hyundai Tucson 1.6 T-GDi',
        'price': '22M FCFA',
        'location': 'Marcory, Abidjan',
        'year': 2022,
        'mileage': '34 000 km',
        'transmission': 'Auto',
        'image': 'img/vehicles/hyundai-tucson.svg',
        'is_verified': True,
        'condition': '',
    },
    {
        'name': 'Mercedes-Benz C300',
        'price': '28.5M FCFA',
        'location': 'Plateau, Abidjan',
        'year': 2021,
        'mileage': '48 200 km',
        'transmission': 'Auto',
        'image': 'img/vehicles/mercedes-c300.svg',
        'is_verified': False,
        'condition': '',
    },
    {
        'name': 'Kia Sportage New Edition',
        'price': '21M FCFA',
        'location': 'Bingerville, Abidjan',
        'year': 2024,
        'mileage': '0 km',
        'transmission': 'Auto',
        'image': 'img/vehicles/kia-sportage.svg',
        'is_verified': False,
        'condition': '',
    },
    {
        'name': 'Ford Explorer XLT',
        'price': '18.5M FCFA',
        'location': 'Yamoussoukro',
        'year': 2019,
        'mileage': '72 000 km',
        'transmission': 'Auto',
        'image': 'img/vehicles/ford-explorer-xlt.svg',
        'is_verified': True,
        'condition': '',
    },
    {
        'name': 'Range Rover Sport HSE',
        'price': '42M FCFA',
        'location': 'Assinie-Mafia',
        'year': 2020,
        'mileage': '55 000 km',
        'transmission': 'Auto',
        'image': 'img/vehicles/range-rover-sport-hse.svg',
        'is_verified': False,
        'condition': '',
    },
]

HOME_STATS = [
    {'end': 1450, 'suffix': '+', 'label': 'Véhicules vendus'},
    {'end': 2300, 'suffix': '', 'label': 'Clients heureux'},
    {'end': 150, 'suffix': '', 'label': "Points d'inspection"},
    {'end': 5000, 'suffix': 'h', 'label': "Heures d'accompagnement"},
]


def home(request):
    """Page d'accueil du parcours public, portée depuis
    _mockups/01_public/desktop/djona_accueil/code.html.

    Les véhicules en avant sont des données statiques en attendant le
    modèle `catalog.Vehicle` (AGENTS.md §10, étape 5).
    """
    context = {
        'featured_vehicles': FEATURED_VEHICLES,
        'stats': HOME_STATS,
    }
    return render(request, 'core/home.html', context)

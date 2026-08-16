import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from apps.catalog.models import Vehicle, VehicleImage

# (brand, model_name, year, price, mileage, fuel_type, transmission, city, condition, is_verified, gradient, description)
VEHICLES = [
    ('Toyota', 'Land Cruiser 300', 2023, 85_000_000, 12_500, 'essence', 'automatique', 'Cocody, Abidjan', 'occasion', True, ('#003b5a', '#1a5276'),
     "Véhicule en excellent état, carnet d'entretien à jour. Jamais accidenté, peinture d'origine. Idéal pour les longs trajets et l'usage familial. Vente pour cause de départ à l'étranger."),
    ('Hyundai', 'Tucson 1.6 T-GDi', 2022, 22_000_000, 34_000, 'essence', 'automatique', 'Marcory, Abidjan', 'occasion', True, ('#26384b', '#3d4f63'),
     "Première main, entretien effectué exclusivement chez le concessionnaire. Climatisation, caméra de recul et régulateur de vitesse fonctionnels."),
    ('Mercedes-Benz', 'C300', 2021, 28_500_000, 48_200, 'essence', 'automatique', 'Plateau, Abidjan', 'occasion', False, ('#1a5276', '#26384b'),
     "Berline élégante et confortable, parfaite pour un usage professionnel. Sellerie cuir, toit ouvrant, système multimédia complet."),
    ('Kia', 'Sportage New Edition', 2024, 21_000_000, 0, 'essence', 'automatique', 'Bingerville, Abidjan', 'neuf', False, ('#3d4f63', '#003b5a'),
     "Véhicule neuf, sous garantie constructeur. Livré avec tous les équipements de série et les dernières aides à la conduite."),
    ('Ford', 'Explorer XLT', 2019, 18_500_000, 72_000, 'essence', 'automatique', 'Yamoussoukro', 'occasion', True, ('#003b5a', '#3d4f63'),
     "SUV familial 7 places, très bon état général. Pneus récents, climatisation performante. Idéal pour les trajets interurbains."),
    ('Range Rover', 'Sport HSE', 2020, 42_000_000, 55_000, 'essence', 'automatique', 'Assinie-Mafia', 'occasion', False, ('#26384b', '#1a5276'),
     "Véhicule haut de gamme, entretien rigoureux. Intérieur cuir impeccable, aucune trace d'usure. Négociable devant le véhicule."),
    ('Toyota', 'Corolla', 2022, 14_000_000, 25_000, 'essence', 'automatique', 'Yopougon, Abidjan', 'occasion', True, ('#003b5a', '#26384b'),
     "Citadine fiable et économique, parfaite pour un premier achat. Faible consommation, entretien peu coûteux."),
    ('Peugeot', '3008', 2023, 19_500_000, 8_000, 'diesel', 'automatique', 'Cocody, Abidjan', 'occasion', True, ('#1a5276', '#3d4f63'),
     "Très faible kilométrage, quasi neuf. Diesel économique, boîte automatique fluide. Dossier d'entretien complet disponible."),
    ('Nissan', 'Qashqai', 2021, 16_000_000, 41_000, 'essence', 'automatique', 'San Pedro', 'occasion', False, ('#26384b', '#003b5a'),
     "Crossover compact et polyvalent. Bon état mécanique, climatisation efficace, idéal pour la ville comme pour les pistes."),
    ('Mercedes-Benz', 'GLE 350', 2024, 55_000_000, 0, 'diesel', 'automatique', 'Plateau, Abidjan', 'neuf', True, ('#003b5a', '#1a5276'),
     "SUV premium neuf, finition Exclusive. Toutes options incluses : sièges massants, affichage tête haute, suspension pneumatique."),
    ('Hyundai', 'i10', 2020, 6_500_000, 38_000, 'essence', 'manuelle', 'Bouaké', 'occasion', False, ('#3d4f63', '#26384b'),
     "Petite citadine idéale pour la ville, très économique en carburant. Entretien facile et pièces disponibles partout."),
    ('Suzuki', 'Jimny', 2023, 13_000_000, 5_000, 'essence', 'manuelle', 'Grand-Bassam', 'occasion', True, ('#1a5276', '#003b5a'),
     "4x4 compact quasi neuf, parfait pour les routes difficiles et les week-ends à la plage. Très peu utilisé."),
]

IMAGE_CAPTIONS = ['Exterieur', 'Interieur', 'Profil']


def hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def make_placeholder_image(brand, caption, gradient):
    width, height = 800, 500
    top, bottom = hex_to_rgb(gradient[0]), hex_to_rgb(gradient[1])
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / height
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    white = (255, 255, 255, 235)
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle([200, 240, 600, 330], radius=24, fill=white)
    odraw.polygon([(280, 240), (320, 180), (480, 180), (520, 240)], fill=white)
    odraw.ellipse([270, 320, 340, 390], fill=(25, 28, 28, 255))
    odraw.ellipse([460, 320, 530, 390], fill=(25, 28, 28, 255))
    odraw.ellipse([290, 340, 320, 370], fill=(225, 227, 227, 255))
    odraw.ellipse([480, 340, 510, 370], fill=(225, 227, 227, 255))
    img.paste(overlay, (0, 0), overlay)

    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=28)
    label = brand.upper()
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(((width - (bbox[2] - bbox[0])) / 2, 110), label, font=font, fill=(255, 255, 255, 200))

    small_font = ImageFont.load_default(size=16)
    caption_text = f'{caption} - Photo a venir'
    bbox = draw.textbbox((0, 0), caption_text, font=small_font)
    draw.text(((width - (bbox[2] - bbox[0])) / 2, height - 50), caption_text, font=small_font, fill=(255, 255, 255, 160))

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return ContentFile(buffer.getvalue())


class Command(BaseCommand):
    help = "Peuple le catalogue avec des véhicules de démonstration (données + images placeholder générées)."

    def handle(self, *args, **options):
        created_count = 0
        for brand, model_name, year, price, mileage, fuel_type, transmission, city, condition, is_verified, gradient, description in VEHICLES:
            vehicle, created = Vehicle.objects.get_or_create(
                brand=brand, model_name=model_name, year=year,
                defaults={
                    'price': price,
                    'mileage': mileage,
                    'fuel_type': fuel_type,
                    'transmission': transmission,
                    'city': city,
                    'condition': condition,
                    'is_verified': is_verified,
                    'description': description,
                    'publish': True,
                },
            )
            if not created:
                continue
            created_count += 1
            for order, caption in enumerate(IMAGE_CAPTIONS):
                image_content = make_placeholder_image(brand, caption, gradient)
                image = VehicleImage(vehicle=vehicle, order=order)
                image.image.save(f'{vehicle.slug}-{order}.jpg', image_content, save=True)
            self.stdout.write(f'  + {vehicle}')

        self.stdout.write(self.style.SUCCESS(
            f'{created_count} véhicule(s) créé(s) ({Vehicle.objects.count()} au total).'
        ))

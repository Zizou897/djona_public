from django.db import migrations

# Catégories du cahier des charges Djona Parts (administrables ensuite depuis le back-office).
CATEGORIES = [
    ('Moteur', 'settings'),
    ('Freinage', 'speed'),
    ('Filtration', 'filter_alt'),
    ('Suspension et direction', 'swap_vert'),
    ('Embrayage et transmission', 'settings_suggest'),
    ('Électricité et électronique', 'electrical_services'),
    ('Refroidissement', 'ac_unit'),
    ('Carrosserie', 'directions_car'),
    ('Éclairage', 'lightbulb'),
    ('Accessoires et consommables', 'build'),
]


def seed(apps, schema_editor):
    PartCategory = apps.get_model('parts', 'PartCategory')
    for order, (name, icon) in enumerate(CATEGORIES, start=1):
        PartCategory.objects.get_or_create(name=name, defaults={'icon': icon, 'order': order})


def unseed(apps, schema_editor):
    apps.get_model('parts', 'PartCategory').objects.filter(name__in=[n for n, _ in CATEGORIES], parts__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [('parts', '0001_initial')]

    operations = [migrations.RunPython(seed, unseed)]

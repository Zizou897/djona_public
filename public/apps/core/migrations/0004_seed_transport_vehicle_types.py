from django.db import migrations

TYPES = ['Camion léger', 'Camion moyen tonnage', 'Camion gros tonnage', 'Camion-benne', 'Semi-remorque', 'Porteur', 'Autre']


def seed(apps, schema_editor):
    TransportVehicleType = apps.get_model('core', 'TransportVehicleType')
    for order, name in enumerate(TYPES):
        TransportVehicleType.objects.get_or_create(name=name, defaults={'order': order})


class Migration(migrations.Migration):
    dependencies = [('core', '0003_transport')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

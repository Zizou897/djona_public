from django.db import migrations


def clear_defaults(apps, schema_editor):
    # Avant l'ajout de ville/état côté vendor, la synchro écrivait toujours
    # « Abidjan » / « occasion » par défaut : ce n'était jamais une vraie info.
    # La synchro suivante remplit les valeurs réelles des annonces publiées.
    Vehicle = apps.get_model('catalog', 'Vehicle')
    Vehicle.objects.filter(source_annonce_id__isnull=False).update(city='', condition='')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_vehicle_city_condition_optional'),
    ]

    operations = [
        migrations.RunPython(clear_defaults, migrations.RunPython.noop),
    ]

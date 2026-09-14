from django.db import migrations

def seed(apps, schema_editor):
    apps.get_model('studio','OrdinalSettings').objects.get_or_create(pk=1)

class Migration(migrations.Migration):
    dependencies=[('studio','0006_ordinalsettings_ordinaledition')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]

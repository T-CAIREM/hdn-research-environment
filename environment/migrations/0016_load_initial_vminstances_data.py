# Generated manually on 2024-07-10 00:00

from django.db import migrations
from django.core.management import call_command


def load_initial_vminstances_data(_apps, _schema_editor):
    call_command("loaddata", "initial_data", app_label="environment")


class Migration(migrations.Migration):
    dependencies = [
        ("environment", "0015_gcpregion_instancetype_vminstance"),
    ]

    # Load initial data from fixtures/initial_data.json file
    operations = [
        migrations.RunPython(load_initial_vminstances_data),
    ]

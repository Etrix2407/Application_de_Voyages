"""Crée la table du cache (limites anti-abus) avec migrate : plus de createcachetable à lancer à la main.

createcachetable ne fait rien si la table existe déjà, ou si le cache n'est pas en base (tests).
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_task_lock"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]

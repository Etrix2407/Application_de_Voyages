from django.db import migrations


def erase_signatures_of_deleted_clients(apps, schema_editor):
    """RGPD : les avis des comptes supprimés avant cette évolution gardaient leur signature en base."""
    Review = apps.get_model("reviews", "Review")
    Review.objects.filter(order__client__isnull=True).update(signature="")


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0004_signature_version_withdrawal'),
    ]

    operations = [
        migrations.RunPython(erase_signatures_of_deleted_clients, migrations.RunPython.noop),
    ]

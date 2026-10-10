from django.db import migrations

from orders.models import client_fingerprint


def fill_client_fingerprint(apps, schema_editor):
    # Demandes existantes dont le client a encore un compte : empreinte de son adresse actuelle.
    # Les demandes déjà anonymisées (client vide) restent sans empreinte.
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(client__isnull=False).select_related("client"):
        order.client_fingerprint = client_fingerprint(order.client.email)
        order.save(update_fields=["client_fingerprint"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_client_fingerprint"),
    ]

    operations = [
        migrations.RunPython(fill_client_fingerprint, migrations.RunPython.noop),
    ]

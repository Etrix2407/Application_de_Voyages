"""Annule les demandes en attente dont le compte client a été supprimé avant la règle actuelle.

Depuis, la suppression d'un compte annule ses demandes en attente (cancel_after_account_deletion).
Les plus anciennes sont restées « En attente » sans client : personne à rappeler ni à prévenir.
"""

from django.db import migrations
from django.utils import timezone

# Textes figés ici : une migration ne dépend pas du code de l'application, qui peut changer.
ACCOUNT_DELETED_REASON = "Compte client supprimé : demande annulée automatiquement."
CLIENT_AUTHOR = "Client"


def cancel_orphan_pending_orders(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    StatusChange = apps.get_model("orders", "StatusChange")
    for order in Order.objects.filter(status="pending", client__isnull=True):
        order.status = "cancelled"
        order.save(update_fields=["status"])
        StatusChange.objects.create(
            order=order,
            status="cancelled",
            changed_at=timezone.now(),
            author=None,
            author_name=CLIENT_AUTHOR,
            internal_reason=ACCOUNT_DELETED_REASON,
            by_client=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0015_constraints_and_indexes"),
    ]

    operations = [
        # Sans retour arrière : rouvrir une demande sans client n'aurait pas de sens.
        migrations.RunPython(cancel_orphan_pending_orders, migrations.RunPython.noop),
    ]

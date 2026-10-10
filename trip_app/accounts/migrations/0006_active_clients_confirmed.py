from django.db import migrations
from django.db.models import F


def mark_active_clients_confirmed(apps, schema_editor):
    """Avant la v5, un client actif avait un compte utilisable (inscription confirmée, ou compte
    créé hors inscription, comme les comptes de démonstration). Désormais, c'est la date de
    confirmation qui autorise les demandes de voyage et protège de la purge : ces comptes la
    reçoivent. Les inscriptions en attente (comptes inactifs) sont traitées par la migration 0007.
    """
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="client", is_active=True, email_confirmed_at__isnull=True).update(
        email_confirmed_at=F("date_joined")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_stable_ordering"),
    ]

    operations = [
        migrations.RunPython(mark_active_clients_confirmed, migrations.RunPython.noop),
    ]

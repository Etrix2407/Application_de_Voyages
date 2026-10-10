from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db import migrations


def delete_pending_sign_ups(apps, schema_editor):
    """Supprime les inscriptions commencées avant la v5 et jamais confirmées.

    Leur compte est inactif et sans mot de passe utilisable (il devait être choisi au clic
    sur le lien) : ce parcours n'existe plus. La personne peut simplement se réinscrire.
    Seuls les clients sont visés : les agents invités (mot de passe inutilisable en attendant
    leur lien) et les membres du personnel désactivés ne sont jamais touchés.
    """
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        role="client",
        is_active=False,
        email_confirmed_at__isnull=True,
        password__startswith=UNUSABLE_PASSWORD_PREFIX,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_active_clients_confirmed"),
    ]

    operations = [
        migrations.RunPython(delete_pending_sign_ups, migrations.RunPython.noop),
    ]

from django.db import migrations

# Texte figé ici : une migration ne dépend pas du code de l'application, qui peut changer.
ACCOUNT_DELETED_REASON = "Compte client supprimé : demande annulée automatiquement."


def move_to_internal_reason(apps, schema_editor):
    # Annulations automatiques existantes : leur motif devient interne (personnel seulement).
    StatusChange = apps.get_model("orders", "StatusChange")
    StatusChange.objects.filter(status="cancelled", reason=ACCOUNT_DELETED_REASON).update(
        reason="", internal_reason=ACCOUNT_DELETED_REASON
    )


def move_back_to_reason(apps, schema_editor):
    StatusChange = apps.get_model("orders", "StatusChange")
    StatusChange.objects.filter(status="cancelled", internal_reason=ACCOUNT_DELETED_REASON).update(
        reason=ACCOUNT_DELETED_REASON, internal_reason=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_status_change_internal_reason'),
    ]

    operations = [
        migrations.RunPython(move_to_internal_reason, move_back_to_reason),
    ]

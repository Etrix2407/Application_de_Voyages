"""Les numéros enregistrés avec le préfixe 00 (ex. 0032…) s'écrivent désormais +32…"""

from django.db import migrations


def international_prefix(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(phone__startswith="00"):
        user.phone = "+" + user.phone[2:]
        user.save(update_fields=["phone"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_email_confirmation"),
    ]

    operations = [
        migrations.RunPython(international_prefix, migrations.RunPython.noop),
    ]

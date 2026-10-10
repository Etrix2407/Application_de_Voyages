from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_promotion"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="client_fingerprint",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=64),
        ),
    ]

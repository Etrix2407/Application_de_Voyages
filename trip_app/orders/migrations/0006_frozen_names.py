from django.db import migrations, models


def copy_current_names(apps, schema_editor):
    # Demandes existantes : on fige les noms tels qu'ils sont aujourd'hui dans le catalogue.
    Order = apps.get_model("orders", "Order")
    OrderActivity = apps.get_model("orders", "OrderActivity")
    for order in Order.objects.select_related("destination__country"):
        order.destination_name = order.destination.name
        order.country_name = order.destination.country.name
        order.save(update_fields=["destination_name", "country_name"])
    for line in OrderActivity.objects.select_related("activity"):
        line.activity_name = line.activity.name
        line.save(update_fields=["activity_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_status_change_by_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="destination_name",
            field=models.CharField(
                default="", max_length=150, verbose_name="nom de la destination au moment de la demande"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="country_name",
            field=models.CharField(default="", max_length=100, verbose_name="nom du pays au moment de la demande"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="orderactivity",
            name="activity_name",
            field=models.CharField(
                default="", max_length=150, verbose_name="nom de l'activité au moment de la demande"
            ),
            preserve_default=False,
        ),
        migrations.RunPython(copy_current_names, migrations.RunPython.noop),
    ]

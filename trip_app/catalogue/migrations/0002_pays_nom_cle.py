"""Unicité du nom de pays insensible à la casse, accents compris.

Sous SQLite, LOWER() ne traite que les lettres ASCII : « PÉROU » et « Pérou »
étaient considérés comme différents. On stocke donc une clé normalisée en Python.
"""

from django.db import migrations, models


def remplir_nom_cle(apps, schema_editor):
    Pays = apps.get_model("catalogue", "Pays")
    for pays in Pays.objects.all():
        pays.nom_cle = pays.nom.strip().casefold()
        pays.save(update_fields=["nom_cle"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="pays", name="pays_nom_unique"),
        migrations.AddField(
            model_name="pays",
            name="nom_cle",
            field=models.CharField(default="", editable=False, max_length=100),
            preserve_default=False,
        ),
        migrations.RunPython(remplir_nom_cle, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pays",
            name="nom_cle",
            field=models.CharField(editable=False, max_length=100, unique=True),
        ),
    ]

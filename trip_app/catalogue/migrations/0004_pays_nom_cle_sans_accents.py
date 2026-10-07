"""La clé d'unicité des pays ignore désormais aussi les accents (« Perou » = « Pérou »)."""

import unicodedata

from django.db import migrations


def _normaliser(texte):
    # Copie figée de config.texte.normaliser : une migration ne doit pas dépendre du code courant.
    decompose = unicodedata.normalize("NFKD", texte.strip())
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()


def recalculer_nom_cle(apps, schema_editor):
    Pays = apps.get_model("catalogue", "Pays")
    noms_par_cle = {}
    for pays in Pays.objects.all():
        noms_par_cle.setdefault(_normaliser(pays.nom), []).append(pays.nom)
    doublons = [noms for noms in noms_par_cle.values() if len(noms) > 1]
    if doublons:
        raise RuntimeError(
            "Ces pays sont des doublons (seuls les accents diffèrent). Renommez ou supprimez-en "
            f"un avant de relancer la migration : {doublons}"
        )
    for pays in Pays.objects.all():
        pays.nom_cle = _normaliser(pays.nom)
        pays.save(update_fields=["nom_cle"])


def restaurer_nom_cle(apps, schema_editor):
    Pays = apps.get_model("catalogue", "Pays")
    for pays in Pays.objects.all():
        pays.nom_cle = pays.nom.strip().casefold()
        pays.save(update_fields=["nom_cle"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0003_favoris"),
    ]

    operations = [
        migrations.RunPython(recalculer_nom_cle, restaurer_nom_cle),
    ]

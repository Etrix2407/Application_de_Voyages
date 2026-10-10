from django.db import migrations, models


class Migration(migrations.Migration):
    """Annulation par l'agence : motif interne en plus de l'explication pour le client.

    Aucune donnée à déplacer : les motifs déjà enregistrés restent dans « reason »,
    désormais l'explication visible par le client, comme avant. Le motif interne
    des annulations existantes reste vide.
    """

    dependencies = [
        ('orders', '0011_merge_20261010_1736'),
    ]

    operations = [
        migrations.AlterField(
            model_name='statuschange',
            name='reason',
            field=models.TextField(blank=True, verbose_name='motif visible par le client'),
        ),
        migrations.AddField(
            model_name='statuschange',
            name='internal_reason',
            field=models.TextField(blank=True, verbose_name='motif interne'),
        ),
    ]

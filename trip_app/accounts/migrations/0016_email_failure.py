"""Type du dernier échec (EmailLog.failure) : remplace la reconnaissance par le texte de last_error.

Les lignes existantes « sans objet » ou « impossibles à refaire » reprennent leur type ; les autres
échecs passent en « autre erreur » (le caractère définitif d'un ancien échec n'est pas connu).
"""

from django.db import migrations, models

OBSOLETE = "Message devenu sans objet (compte supprimé ou modifié depuis) : il n'a pas été renvoyé."
NOT_REBUILDABLE = "Ce type d'e-mail ne peut pas être renvoyé."


def fill_failure(apps, schema_editor):
    EmailLog = apps.get_model("accounts", "EmailLog")
    EmailLog.objects.filter(last_error=OBSOLETE).update(failure="obsolete")
    EmailLog.objects.filter(last_error=NOT_REBUILDABLE).update(failure="not_rebuildable")
    EmailLog.objects.exclude(last_error="").filter(failure="").update(failure="other")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_email_texts'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='failure',
            field=models.CharField(blank=True, choices=[('recipient_refused', 'Destinataire refusé (adresse inconnue ou invalide)'), ('unreachable', "Serveur d'envoi injoignable"), ('timeout', 'Délai dépassé'), ('other', 'Autre erreur'), ('obsolete', 'Message devenu sans objet'), ('not_rebuildable', "Type d'e-mail impossible à renvoyer")], max_length=20, verbose_name='type du dernier échec'),
        ),
        migrations.RunPython(fill_failure, migrations.RunPython.noop),
    ]

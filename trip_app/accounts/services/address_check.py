"""« Adresse à vérifier » (v5) : client dont plusieurs messages différents n'ont pas pu partir.

Calculé à partir du journal, sans champ à tenir à jour : on compte les messages arrivés à
l'état « échec » après toutes leurs tentatives, dont le dernier échec est un refus définitif du
destinataire (une panne du serveur d'envoi ne compte pas), envoyés à l'adresse actuelle du client
et non suivis d'un envoi réussi vers cette adresse. Le marqueur disparaît donc de lui-même au
prochain envoi réussi, ou quand le client change d'adresse.
"""

from django.db.models import Count, Exists, OuterRef, QuerySet

from accounts.models import EmailFailure, EmailLog, EmailStatus
from accounts.services.emails import MAX_ATTEMPTS

ADDRESS_CHECK_FAILURES = 3


def with_address_to_check(users: QuerySet) -> QuerySet:
    """Ajoute à chaque compte l'attribut booléen `address_to_check`."""
    later_success = EmailLog.objects.filter(
        user=OuterRef("user"),
        recipient=OuterRef("recipient"),
        status=EmailStatus.SENT,
        last_attempt_at__gt=OuterRef("last_attempt_at"),
    )
    # Le seuil est appliqué dans la sous-requête (HAVING) : elle n'est exécutée qu'une fois par compte.
    enough_failures = (
        EmailLog.objects.filter(
            user=OuterRef("pk"),
            recipient=OuterRef("email"),
            status=EmailStatus.FAILED,
            failure=EmailFailure.RECIPIENT_REFUSED,
            attempts__gte=MAX_ATTEMPTS,
        )
        .filter(~Exists(later_success))
        .order_by()
        .values("user")
        .annotate(total=Count("pk"))
        .filter(total__gte=ADDRESS_CHECK_FAILURES)
    )
    return users.annotate(address_to_check=Exists(enough_failures))

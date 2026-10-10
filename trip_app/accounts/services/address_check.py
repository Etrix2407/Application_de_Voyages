"""« Adresse à vérifier » (v5) : client dont plusieurs messages différents n'ont pas pu partir.

Calculé à partir du journal, sans champ à tenir à jour : on compte les messages arrivés à
l'état « échec » après toutes leurs tentatives, envoyés à l'adresse actuelle du client et non
suivis d'un envoi réussi vers cette adresse. Le marqueur disparaît donc de lui-même au prochain
envoi réussi, ou quand le client change d'adresse.
"""

from django.db.models import BooleanField, Count, Exists, ExpressionWrapper, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from accounts.models import EmailLog, EmailStatus
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
    failures = (
        EmailLog.objects.filter(
            user=OuterRef("pk"), recipient=OuterRef("email"), status=EmailStatus.FAILED, attempts__gte=MAX_ATTEMPTS
        )
        .filter(~Exists(later_success))
        .order_by()
        .values("user")
        .annotate(total=Count("pk"))
        .values("total")
    )
    return users.annotate(email_failures=Coalesce(Subquery(failures), 0)).annotate(
        address_to_check=ExpressionWrapper(Q(email_failures__gte=ADDRESS_CHECK_FAILURES), output_field=BooleanField())
    )

"""RGPD : effacement des données des comptes supprimés hors du modèle utilisateur, et durée de conservation du journal."""

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import EmailLog, User

# Journal des e-mails conservé 1 an (Recap 5).
EMAIL_LOG_RETENTION = timedelta(days=365)


def erase_email_log_of(user: User) -> None:
    """Journal des e-mails : les lignes restent (statistiques anonymes), sans adresse ni lien au compte."""
    EmailLog.objects.filter(Q(user=user) | Q(recipient=user.email)).update(recipient="", user=None)


def purge_old_email_log(now: datetime | None = None) -> int:
    """Efface les lignes du journal de plus d'un an. Renvoie le nombre de lignes effacées."""
    limit = (now or timezone.now()) - EMAIL_LOG_RETENTION
    deleted, _ = EmailLog.objects.filter(created_at__lt=limit).delete()
    return deleted

"""RGPD : effacement des données des comptes supprimés hors du modèle utilisateur."""

from django.db.models import Q

from accounts.models import EmailLog, User


def erase_email_log_of(user: User) -> None:
    """Journal des e-mails : les lignes restent (statistiques anonymes), sans adresse ni lien au compte."""
    EmailLog.objects.filter(Q(user=user) | Q(recipient=user.email)).update(recipient="", user=None)

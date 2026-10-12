"""Chiffres des e-mails du tableau de pilotage (Recap 6), indépendants de la période choisie.

- E-mails en échec sur les 7 derniers jours glissants, comptés à la date de leur dernière tentative :
  c'est la date de l'échec (un e-mail créé il y a 10 jours dont le renvoi vient d'échouer compte).
  Tous les échecs comptent, même ceux qui ne peuvent plus être renvoyés (compte supprimé, message
  devenu sans objet) : le chiffre mesure les problèmes d'envoi, pas le travail restant.
- Clients « adresse à vérifier » : même règle que la liste des clients (accounts.services.address_check).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from accounts.models import EmailLog, EmailStatus, Role, User
from accounts.services.address_check import with_address_to_check

FAILURE_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class EmailFigures:
    recent_failures: int
    addresses_to_check: int


def email_figures(now: datetime | None = None) -> EmailFigures:
    since = (now or timezone.now()) - FAILURE_WINDOW
    clients = User.objects.filter(role=Role.CLIENT)
    return EmailFigures(
        recent_failures=EmailLog.objects.filter(status=EmailStatus.FAILED, last_attempt_at__gte=since).count(),
        addresses_to_check=with_address_to_check(clients).filter(address_to_check=True).count(),
    )

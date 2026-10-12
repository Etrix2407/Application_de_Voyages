"""Section « Clients et e-mails » du tableau de pilotage : réunit les deux groupes de chiffres."""

from dataclasses import dataclass

from dashboard.services.clients import ClientFigures, client_figures
from dashboard.services.emails import EmailFigures, email_figures
from dashboard.services.periods import Period


@dataclass(frozen=True)
class ClientsEmailsSection:
    clients: ClientFigures
    emails: EmailFigures


def clients_emails_section(period: Period) -> ClientsEmailsSection:
    return ClientsEmailsSection(clients=client_figures(period), emails=email_figures())

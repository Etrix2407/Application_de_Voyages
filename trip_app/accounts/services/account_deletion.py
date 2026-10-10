"""Suppression d'un compte, avec un dernier e-mail qui l'annonce à son titulaire."""

from django.db import transaction

from accounts.models import EmailKind, User
from accounts.services.emails import send_email

# Un type d'e-mail par cas : chaque texte est différent (et sera modifiable séparément).
TEMPLATES = {
    EmailKind.ACCOUNT_DELETED: "accounts/emails/account_deleted.txt",
    EmailKind.UNCONFIRMED_ACCOUNT_DELETED: "accounts/emails/unconfirmed_account_deleted.txt",
    EmailKind.STAFF_ACCOUNT_DELETED: "accounts/emails/staff_account_deleted.txt",
}


def delete_account(user: User, kind: EmailKind = EmailKind.ACCOUNT_DELETED) -> None:
    """Supprime le compte et prévient son titulaire : ce message est le dernier qu'il reçoit.

    `kind` : suppression par le client (défaut), purge d'un compte jamais confirmé,
    ou suppression d'un membre du personnel par l'administrateur.

    L'e-mail est préparé avant la suppression, pendant que l'adresse existe encore, et part
    après la validation de la transaction : seulement si la suppression a réussi (aussi hors
    requête, par exemple dans une commande planifiée).
    La suppression efface ensuite l'adresse de la ligne du journal (accounts/signals.py, qui la
    retrouve par son destinataire) ; le message déjà préparé garde son destinataire.
    Les demandes en attente sont annulées sans e-mail (orders/signals.py).
    """
    with transaction.atomic():
        # Pas de compte lié (user) : il n'existera plus quand le journal notera le résultat de l'envoi.
        send_email(user.email, kind, TEMPLATES[kind], {"user": user})
        user.delete()

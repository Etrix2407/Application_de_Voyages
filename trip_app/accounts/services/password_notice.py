"""Alerte de sécurité envoyée après chaque changement de mot de passe (clients et personnel)."""

from accounts.models import EmailKind, User
from accounts.services.emails import send_email


def send_password_changed_notice(user: User) -> None:
    """« Si ce n'est pas vous, contactez-nous » : pas envoyé à la toute première définition (invitation d'un agent)."""
    send_email(
        user.email,
        EmailKind.PASSWORD_CHANGED,
        "accounts/emails/password_changed.txt",
        {"user": user},
        user=user,
    )

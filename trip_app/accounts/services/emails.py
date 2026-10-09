"""Envoi des e-mails des comptes : liens de mot de passe et confirmation d'inscription."""

import logging
import smtplib

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import User

logger = logging.getLogger(__name__)


def send_email(subject: str, template_name: str, context: dict, to: str) -> bool:
    """Envoie un e-mail texte. Renvoie False si l'envoi a échoué.

    L'erreur est journalisée avec sa cause ; l'appelant prévient l'utilisateur
    au lieu d'afficher une erreur 500.
    """
    body = render_to_string(template_name, context)
    try:
        send_mail(subject, body, None, [to])
    except (OSError, smtplib.SMTPException):
        logger.exception("Échec de l'envoi de l'e-mail « %s » à %s", subject, to)
        return False
    return True


def send_password_link(request, user: User, subject: str, template_name: str) -> bool:
    """Envoie un lien valable 1 heure (PASSWORD_RESET_TIMEOUT) ; personne d'autre ne voit le mot de passe."""
    link = request.build_absolute_uri(
        reverse(
            "password_reset_confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )
    )
    return send_email(subject, template_name, {"user": user, "link": link}, user.email)

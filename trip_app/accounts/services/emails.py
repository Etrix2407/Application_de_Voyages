"""Envoi d'un lien permettant à l'utilisateur de choisir lui-même son mot de passe."""

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


def send_password_link(request, user: User, subject: str, template_name: str) -> bool:
    """Envoie un lien valable 1 heure (PASSWORD_RESET_TIMEOUT) ; personne d'autre ne voit le mot de passe.

    Renvoie False si l'e-mail n'a pas pu partir : l'erreur est journalisée et l'appelant
    prévient l'utilisateur, au lieu d'afficher une erreur 500.
    """
    link = request.build_absolute_uri(
        reverse(
            "password_reset_confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )
    )
    body = render_to_string(template_name, {"user": user, "link": link})
    try:
        send_mail(subject, body, None, [user.email])
    except (OSError, smtplib.SMTPException):
        logger.exception("Échec de l'envoi du lien de mot de passe à %s", user.email)
        return False
    return True

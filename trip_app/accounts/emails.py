"""Envoi d'un lien permettant à l'utilisateur de choisir lui-même son mot de passe."""

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


def send_password_link(request, user: User, subject: str, template_name: str) -> None:
    """Le lien est valable 1 heure (PASSWORD_RESET_TIMEOUT) ; personne d'autre ne voit le mot de passe."""
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
    send_mail(subject, body, None, [user.email])

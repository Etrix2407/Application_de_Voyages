"""Envoi d'un lien permettant à l'utilisateur de choisir lui-même son mot de passe."""

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import Utilisateur


def envoyer_lien_mot_de_passe(request, utilisateur: Utilisateur, sujet: str, gabarit: str) -> None:
    """Le lien est valable 1 heure (PASSWORD_RESET_TIMEOUT) ; personne d'autre ne voit le mot de passe."""
    lien = request.build_absolute_uri(
        reverse(
            "reinitialisation",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(utilisateur.pk)),
                "token": default_token_generator.make_token(utilisateur),
            },
        )
    )
    corps = render_to_string(gabarit, {"utilisateur": utilisateur, "lien": lien})
    send_mail(sujet, corps, None, [utilisateur.email])

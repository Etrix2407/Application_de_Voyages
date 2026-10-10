"""Liens pour choisir un mot de passe, envoyés par e-mail (agents, clients)."""

from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import EmailKind, User
from accounts.services.emails import send_email


def password_token(user: User) -> dict:
    """Identifiant et jeton du lien (valable 1 heure, PASSWORD_RESET_TIMEOUT)."""
    return {"uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user)}


def password_link_path(user: User) -> str:
    """Chemin du lien pour choisir un mot de passe (à rendre absolu)."""
    return reverse("password_reset_confirm", kwargs=password_token(user))


def send_password_link(request, user: User, kind: EmailKind, template_name: str) -> bool:
    """Envoie un lien valable 1 heure (PASSWORD_RESET_TIMEOUT) ; personne d'autre ne voit le mot de passe."""
    link = request.build_absolute_uri(password_link_path(user))
    return send_email(user.email, kind, template_name, {"user": user, "link": link}, user=user)

"""Gestion des comptes du personnel par l'administrateur."""

from django.core.exceptions import ValidationError

from .emails import send_password_link
from .models import User


def check_not_self(target: User, actor: User) -> None:
    """Un administrateur ne peut pas se désactiver, se supprimer ni changer son rôle.

    Comme seul un administrateur actif peut agir, cette règle garantit qu'il reste
    toujours au moins un administrateur actif.
    """
    if target.pk == actor.pk:
        raise ValidationError(
            "Vous ne pouvez pas effectuer cette action sur votre propre compte.",
            code="action_on_self",
        )


def send_activation_link(request, agent: User) -> None:
    """Envoie à l'agent un lien pour choisir son mot de passe."""
    send_password_link(
        request, agent, "Activation de votre compte", "accounts/agent_activation_email.txt"
    )

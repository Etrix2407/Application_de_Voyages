"""Gestion des comptes du personnel par l'administrateur."""

from django.core.exceptions import ValidationError

from accounts.models import EmailKind, User
from accounts.services.password_links import send_password_link


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


def send_activation_link(request, agent: User) -> bool:
    """Envoie à l'agent un lien pour choisir son mot de passe ; False si l'envoi a échoué."""
    return send_password_link(
        request, agent, EmailKind.AGENT_ACTIVATION, "accounts/emails/agent_activation.txt"
    )

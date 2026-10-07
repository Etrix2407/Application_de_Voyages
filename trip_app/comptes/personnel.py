"""Gestion des comptes du personnel par l'administrateur."""

from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import Utilisateur


def verifier_action_sur_soi(cible: Utilisateur, acteur: Utilisateur) -> None:
    """Un administrateur ne peut pas se désactiver, se supprimer ni changer son rôle.

    Comme seul un administrateur actif peut agir, cette règle garantit qu'il reste
    toujours au moins un administrateur actif.
    """
    if cible.pk == acteur.pk:
        raise ValidationError(
            "Vous ne pouvez pas effectuer cette action sur votre propre compte.",
            code="action_sur_soi",
        )


def envoyer_lien_activation(request, agent: Utilisateur) -> None:
    """Envoie à l'agent un lien (valable 1 heure) pour choisir son mot de passe."""
    lien = request.build_absolute_uri(
        reverse(
            "reinitialisation",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(agent.pk)),
                "token": default_token_generator.make_token(agent),
            },
        )
    )
    corps = render_to_string("comptes/email_activation_agent.txt", {"agent": agent, "lien": lien})
    send_mail("Activation de votre compte", corps, None, [agent.email])

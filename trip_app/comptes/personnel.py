"""Gestion des comptes du personnel par l'administrateur."""

from django.core.exceptions import ValidationError

from .emails import envoyer_lien_mot_de_passe
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
    """Envoie à l'agent un lien pour choisir son mot de passe."""
    envoyer_lien_mot_de_passe(
        request, agent, "Activation de votre compte", "comptes/email_activation_agent.txt"
    )

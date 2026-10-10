"""Liens pour choisir un mot de passe, envoyés par e-mail (agents, clients)."""

from datetime import timedelta

from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_encode

from accounts.models import EmailKind, User
from accounts.services.emails import send_email

# Invitation d'un agent : 7 jours (Recap 5). Les autres liens gardent 1 heure (PASSWORD_RESET_TIMEOUT).
INVITATION_LINK_MAX_AGE = timedelta(days=7)


class AgentInvitationTokenGenerator(PasswordResetTokenGenerator):
    """Jeton de l'invitation d'un agent : comme « mot de passe oublié », mais valable 7 jours.

    Django lit la durée dans PASSWORD_RESET_TIMEOUT, partagé avec « mot de passe oublié » qui doit
    rester à 1 heure : la durée est donc vérifiée ici. Le jeton ne sert qu'une fois (il dépend du
    mot de passe et de la dernière connexion) et ne vaut pas pour « mot de passe oublié » (autre sel).
    """

    key_salt = "accounts.agent-invitation"

    def check_token(self, user, token) -> bool:
        if not (user and token):
            return False
        try:
            timestamp = base36_to_int(token.split("-")[0])
        except ValueError:
            return False
        if self._num_seconds(self._now()) - timestamp > INVITATION_LINK_MAX_AGE.total_seconds():
            return False
        return any(
            constant_time_compare(self._make_token_with_timestamp(user, timestamp, secret), token)
            for secret in [self.secret, *self.secret_fallbacks]
        )


agent_invitation_token_generator = AgentInvitationTokenGenerator()


def send_password_link(request, user: User, kind: EmailKind, template_name: str) -> bool:
    """Envoie un lien valable 1 heure (PASSWORD_RESET_TIMEOUT) ; personne d'autre ne voit le mot de passe."""
    return _send_link(request, user, kind, template_name, "password_reset_confirm", default_token_generator)


def send_staff_link(request, member: User, kind: EmailKind, template_name: str) -> bool:
    """Envoie à un membre du personnel un lien valable 7 jours pour choisir son mot de passe (pas de mot de passe provisoire)."""
    return _send_link(request, member, kind, template_name, "activate_account", agent_invitation_token_generator)


def _send_link(
    request, user: User, kind: EmailKind, template_name: str, url_name: str, token_generator
) -> bool:
    link = request.build_absolute_uri(
        reverse(
            url_name,
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": token_generator.make_token(user),
            },
        )
    )
    return send_email(user.email, kind, template_name, {"user": user, "link": link}, user=user)

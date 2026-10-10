"""Reconstruction des e-mails des comptes, pour les nouvelles tentatives et le renvoi manuel.

Chaque fonction reprend les règles de l'envoi d'origine et renvoie None si le message n'a plus
de raison d'être. Un message qui contient un lien de sécurité ne part qu'à l'adresse actuelle
du compte : jamais à une ancienne adresse.
"""

from urllib.parse import urlsplit

from django.urls import reverse

from accounts.models import EmailKind, EmailLog, User
from accounts.services.email_retry import RebuiltEmail, rebuilder
from accounts.services.emails import site_url
from accounts.services.password_links import password_link_path, password_token, staff_link_path
from accounts.services.sign_up import make_confirmation_token, notification_context


def _account_at_recipient(log: EmailLog) -> User | None:
    """Compte lié, s'il a toujours l'adresse à laquelle le message était destiné."""
    user = log.user
    return user if user is not None and user.email == log.recipient else None


@rebuilder(EmailKind.SIGN_UP_CONFIRMATION)
def _sign_up_confirmation(log: EmailLog) -> RebuiltEmail | None:
    user = _account_at_recipient(log)
    if user is None or not user.is_awaiting_confirmation:
        return None
    link = site_url(reverse("confirm_sign_up", args=[make_confirmation_token(user)]))
    return RebuiltEmail(
        "accounts/emails/sign_up_confirmation.txt",
        {**notification_context(user, site_url), "confirmation_link": link},
    )


@rebuilder(EmailKind.SIGN_UP_EXISTING)
def _sign_up_existing(log: EmailLog) -> RebuiltEmail | None:
    user = _account_at_recipient(log)
    if user is None:
        return None
    return RebuiltEmail("accounts/emails/sign_up_existing.txt", notification_context(user, site_url))


# EMAIL_CHANGE_CONFIRMATION n'est volontairement pas reconstruit : l'ancienne adresse, qui fait
# partie du lien, n'est pas conservée. En cas d'échec, le client refait sa demande.


@rebuilder(EmailKind.EMAIL_CHANGE_NOTICE)
def _email_change_notice(log: EmailLog) -> RebuiltEmail | None:
    # Alerte sans lien, destinée à l'adresse d'alors (elle a pu changer depuis).
    if log.user is None:
        return None
    return RebuiltEmail("accounts/emails/email_change_notice.txt", {"user": log.user})


@rebuilder(EmailKind.PASSWORD_RESET)
def _password_reset(log: EmailLog) -> RebuiltEmail | None:
    user = _account_at_recipient(log)
    # Mêmes conditions que « Mot de passe oublié » (PasswordResetForm.get_users).
    if user is None or not user.is_active or not user.has_usable_password():
        return None
    token = password_token(user)
    site = urlsplit(site_url("/"))
    return RebuiltEmail(
        "accounts/emails/password_reset.txt",
        {"user": user, "uid": token["uidb64"], "token": token["token"], "protocol": site.scheme, "domain": site.netloc},
    )


@rebuilder(EmailKind.CLIENT_PASSWORD_LINK)
def _client_password_link(log: EmailLog) -> RebuiltEmail | None:
    user = _account_at_recipient(log)
    if user is None or not user.is_client:
        return None
    return RebuiltEmail("accounts/emails/client_password.txt", {"user": user, "link": site_url(password_link_path(user))})


@rebuilder(EmailKind.AGENT_ACTIVATION)
def _agent_activation(log: EmailLog) -> RebuiltEmail | None:
    user = _account_at_recipient(log)
    # Invitation : sans objet si l'agent a déjà choisi son mot de passe. Lien neuf de 7 jours.
    if user is None or not user.is_staff_member or not user.is_active or user.has_usable_password():
        return None
    return RebuiltEmail("accounts/emails/agent_activation.txt", {"user": user, "link": site_url(staff_link_path(user))})


@rebuilder(EmailKind.STAFF_PASSWORD_LINK)
def _staff_password_link(log: EmailLog) -> RebuiltEmail | None:
    user = _account_at_recipient(log)
    # Membre qui a déjà un mot de passe (sinon c'est une invitation). Lien neuf de 7 jours.
    if user is None or not user.is_staff_member or not user.is_active or not user.has_usable_password():
        return None
    return RebuiltEmail("accounts/emails/staff_password.txt", {"user": user, "link": site_url(staff_link_path(user))})


@rebuilder(EmailKind.PASSWORD_CHANGED)
def _password_changed(log: EmailLog) -> RebuiltEmail | None:
    # Alerte sans lien, destinée à l'adresse d'alors (elle a pu changer depuis).
    if log.user is None:
        return None
    return RebuiltEmail("accounts/emails/password_changed.txt", {"user": log.user})


# ACCOUNT_DELETED, UNCONFIRMED_ACCOUNT_DELETED et STAFF_ACCOUNT_DELETED ne sont volontairement pas
# reconstruits : l'adresse est effacée du journal à la suppression du compte (RGPD).



"""Reconstruction des e-mails des comptes, pour les nouvelles tentatives et le renvoi manuel.

Chaque fonction reprend les règles de l'envoi d'origine et renvoie None si le message n'a plus
de raison d'être. Un message qui contient un lien de sécurité ne part qu'à l'adresse actuelle
du compte : jamais à une ancienne adresse.
"""

from collections.abc import Callable

from accounts.models import EmailKind, EmailLog, User
from accounts.services.email_retry import RebuiltEmail, rebuilder
from accounts.services.emails import site_url
from accounts.services.password_links import password_link_path, staff_link_fields, staff_link_path
from accounts.services.sign_up import account_fields, confirmation_fields


def account_at_recipient(log: EmailLog) -> User | None:
    """Compte lié, s'il a toujours l'adresse à laquelle le message était destiné."""
    user = log.user
    return user if user is not None and user.email == log.recipient else None


@rebuilder(EmailKind.SIGN_UP_CONFIRMATION)
def _sign_up_confirmation(log: EmailLog) -> RebuiltEmail | None:
    user = account_at_recipient(log)
    if user is None or not user.is_awaiting_confirmation:
        return None
    return RebuiltEmail(confirmation_fields(user))


@rebuilder(EmailKind.SIGN_UP_EXISTING)
def _sign_up_existing(log: EmailLog) -> RebuiltEmail | None:
    user = account_at_recipient(log)
    if user is None:
        return None
    return RebuiltEmail(account_fields(user))


# EMAIL_CHANGE_CONFIRMATION n'est volontairement pas reconstruit : l'ancienne adresse, qui fait
# partie du lien, n'est pas conservée. En cas d'échec, le client refait sa demande.


@rebuilder(EmailKind.EMAIL_CHANGE_NOTICE)
@rebuilder(EmailKind.PASSWORD_CHANGED)
def _security_notice(log: EmailLog) -> RebuiltEmail | None:
    # Alerte sans lien, destinée à l'adresse d'alors (elle a pu changer depuis).
    if log.user is None:
        return None
    return RebuiltEmail({"prénom": log.user.first_name})


def _password_link(log: EmailLog, may_receive: Callable[[User], bool]) -> RebuiltEmail | None:
    """Lien neuf d'une heure pour choisir un mot de passe, si le compte peut encore le recevoir."""
    user = account_at_recipient(log)
    if user is None or not may_receive(user):
        return None
    return RebuiltEmail({"prénom": user.first_name, "lien": site_url(password_link_path(user))})


@rebuilder(EmailKind.PASSWORD_RESET)
def _password_reset(log: EmailLog) -> RebuiltEmail | None:
    # Mêmes conditions que « Mot de passe oublié » (PasswordResetForm.get_users).
    return _password_link(log, lambda user: user.is_active and user.has_usable_password())


@rebuilder(EmailKind.CLIENT_PASSWORD_LINK)
def _client_password_link(log: EmailLog) -> RebuiltEmail | None:
    return _password_link(log, lambda user: user.is_client)


def _staff_link(log: EmailLog, has_password: bool) -> RebuiltEmail | None:
    """Lien neuf de 7 jours pour un membre actif du personnel, selon qu'il a déjà un mot de passe ou non."""
    user = account_at_recipient(log)
    if user is None or not user.is_staff_member or not user.is_active or user.has_usable_password() != has_password:
        return None
    return RebuiltEmail(staff_link_fields(user, site_url(staff_link_path(user))))


@rebuilder(EmailKind.AGENT_ACTIVATION)
def _agent_activation(log: EmailLog) -> RebuiltEmail | None:
    # Invitation : sans objet si l'agent a déjà choisi son mot de passe.
    return _staff_link(log, has_password=False)


@rebuilder(EmailKind.STAFF_PASSWORD_LINK)
def _staff_password_link(log: EmailLog) -> RebuiltEmail | None:
    # Membre qui a déjà un mot de passe (sinon c'est une invitation).
    return _staff_link(log, has_password=True)


# ACCOUNT_DELETED, UNCONFIRMED_ACCOUNT_DELETED et STAFF_ACCOUNT_DELETED ne sont volontairement pas
# reconstruits : l'adresse est effacée du journal à la suppression du compte (RGPD).

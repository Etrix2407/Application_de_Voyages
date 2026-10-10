"""Changement d'adresse e-mail d'un client, confirmé par un lien envoyé à la nouvelle adresse.

Le client ressaisit son mot de passe (formulaire), puis :
- la nouvelle adresse reçoit un lien ; l'adresse ne change qu'au clic ;
- l'ancienne adresse est prévenue (si ce n'est pas lui, il change son mot de passe) ;
- la réponse est toujours la même : rien ne révèle si la nouvelle adresse est déjà prise.
"""

from datetime import timedelta

from django.core import signing
from django.db import transaction
from django.urls import reverse

from accounts.models import Role, User, normalize_email_address
from accounts.services.emails import send_email
from accounts.signals import email_changed
from accounts.services.throttling import confirmation_emails

LINK_MAX_AGE = timedelta(hours=24)
_TOKEN_SALT = "accounts.email-change"


def request_email_change(request, user: User, new_email: str) -> None:
    new_email = normalize_email_address(new_email)
    _notify_current_address(user)
    if User.objects.filter(email=new_email).exists() or confirmation_emails.is_locked(new_email):
        return
    confirmation_emails.record(new_email)
    token = signing.dumps({"id": user.pk, "old": user.email, "new": new_email}, salt=_TOKEN_SALT)
    link = request.build_absolute_uri(reverse("confirm_email_change", args=[token]))
    send_email(
        "Confirmez votre nouvelle adresse e-mail",
        "accounts/emails/email_change_confirmation.txt",
        {"user": user, "link": link},
        new_email,
    )


def pending_email_change(token: str) -> tuple[User, str] | None:
    """Client et nouvelle adresse visés par le lien, s'il est valide et toujours d'actualité ; sinon None."""
    try:
        data = signing.loads(token, salt=_TOKEN_SALT, max_age=LINK_MAX_AGE)
    except signing.BadSignature:  # comprend les liens expirés
        return None
    # L'ancienne adresse doit être inchangée : un lien plus ancien ne s'applique plus.
    # Réservé aux clients : le personnel ne change pas d'adresse par ce parcours.
    user = User.objects.filter(pk=data.get("id"), email=data.get("old"), role=Role.CLIENT).first()
    if user is None or User.objects.filter(email=data.get("new")).exists():
        return None
    return user, data["new"]


@transaction.atomic
def apply_email_change(user: User, new_email: str) -> None:
    """Applique un changement obtenu par pending_email_change (lien déjà vérifié)."""
    user.email = new_email
    user.save(update_fields=["email"])
    email_changed.send(sender=User, user=user)


def _notify_current_address(user: User) -> None:
    send_email(
        "Demande de changement de votre adresse e-mail",
        "accounts/emails/email_change_notice.txt",
        {"user": user},
        user.email,
    )

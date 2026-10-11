"""Désinscription en un clic des e-mails promotionnels (obligation légale, Recap 5).

Chaque e-mail promotionnel contient un lien personnel, signé, sans date d'expiration : il ne sert
qu'à retirer le consentement, il peut donc rester valable. Le lien figure dans le texte et dans
les en-têtes List-Unsubscribe (désinscription directe depuis la messagerie, RFC 8058).
"""

from django.core import signing
from django.urls import reverse

from accounts.models import Role, User
from accounts.services.emails import site_url

_TOKEN_SALT = "accounts.promotional-emails-unsubscribe"


def unsubscribe_link(user: User) -> str:
    """Lien absolu de désinscription du compte."""
    token = signing.dumps({"id": user.pk}, salt=_TOKEN_SALT)
    return site_url(reverse("unsubscribe", args=[token]))


def unsubscribe_headers(user: User) -> dict[str, str]:
    """En-têtes qui permettent à la messagerie de proposer la désinscription en un clic."""
    return {
        "List-Unsubscribe": f"<{unsubscribe_link(user)}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def client_from_token(token: str) -> User | None:
    """Client visé par le lien, ou None si le lien est faux ou si le compte n'existe plus."""
    try:
        data = signing.loads(token, salt=_TOKEN_SALT)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=data.get("id"), role=Role.CLIENT).first()


def unsubscribe(user: User) -> None:
    """Retire le consentement ; sans effet si le client est déjà désinscrit."""
    user.set_promotional_emails_consent(False)
    user.save(update_fields=["accepts_promotional_emails", "promotional_emails_choice_date"])

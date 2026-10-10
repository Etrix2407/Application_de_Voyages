"""Inscription des clients avec confirmation de l'adresse e-mail.

Le parcours ne révèle jamais si une adresse est déjà inscrite :
- adresse nouvelle (ou compte non confirmé) : compte créé avec le mot de passe choisi
  + lien de confirmation ;
- adresse déjà confirmée : aucun compte créé, la propriétaire est prévenue par e-mail.
Le compte est utilisable tout de suite (connexion, catalogue, favoris), mais le client
ne peut pas envoyer de demande de voyage tant que son adresse n'est pas confirmée.
Une nouvelle inscription avec l'adresse d'un compte non confirmé remplace ce compte :
la vraie propriétaire de l'adresse peut toujours reprendre la main.
La page de confirmation affiche les données du compte et demande un clic sur un bouton :
la propriétaire de l'adresse ne confirme pas sans le savoir un compte créé par un tiers.
"""

from collections.abc import Callable
from datetime import timedelta

from django.core import signing
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailKind, Role, User, normalize_email_address
from accounts.services.emails import send_email
from accounts.services.throttling import confirmation_emails

CONFIRMATION_MAX_AGE = timedelta(hours=48)
UNCONFIRMED_RETENTION = timedelta(days=30)
_TOKEN_SALT = "accounts.sign-up-confirmation"
_PERSONAL_FIELDS = ("first_name", "last_name", "phone", "birth_date")


def make_confirmation_token(user: User) -> str:
    # L'adresse fait partie du jeton : un lien ne vaut que pour l'adresse qui l'a reçu.
    # La date d'inscription aussi : un lien ne vaut que pour les données envoyées avec lui.
    return signing.dumps(
        {"id": user.pk, "email": user.email, "joined": user.date_joined.isoformat()}, salt=_TOKEN_SALT
    )


def user_from_token(token: str) -> User | None:
    """Compte visé par le lien, ou None si le lien est faux, expiré ou ne correspond plus."""
    try:
        data = signing.loads(token, salt=_TOKEN_SALT, max_age=CONFIRMATION_MAX_AGE)
    except signing.BadSignature:  # comprend les liens expirés
        return None
    user = User.objects.filter(pk=data.get("id"), email=data.get("email"), role=Role.CLIENT).first()
    if user is None or user.date_joined.isoformat() != data.get("joined"):
        return None
    return user


def request_sign_up(request, form) -> None:
    """Traite un formulaire d'inscription valide, sans révéler si l'adresse existe."""
    email = normalize_email_address(form.cleaned_data["email"])
    existing = User.objects.filter(email=email).first()
    if existing and not existing.is_awaiting_confirmation:
        _notify(request, existing, EmailKind.SIGN_UP_EXISTING, "accounts/emails/sign_up_existing.txt")
        return

    user = User(email=email, role=Role.CLIENT, consent_date=timezone.now())
    for field in _PERSONAL_FIELDS:
        setattr(user, field, form.cleaned_data.get(field))
    user.set_password(form.cleaned_data["password1"])
    with transaction.atomic():
        if existing:
            # Compte non confirmé : supprimé (sessions et favoris compris) et remplacé.
            # Ses anciens liens de confirmation ne valent plus rien (autre compte).
            existing.delete()
        user.save()
    send_confirmation(request, user)


def send_confirmation(request, user: User) -> bool:
    """Envoie le lien de confirmation. Renvoie False s'il n'est pas parti (limite ou panne)."""
    link = request.build_absolute_uri(reverse("confirm_sign_up", args=[make_confirmation_token(user)]))
    return _notify(
        request,
        user,
        EmailKind.SIGN_UP_CONFIRMATION,
        "accounts/emails/sign_up_confirmation.txt",
        {"confirmation_link": link},
    )


def resend_confirmation(request, email: str) -> None:
    """Renvoie le lien si l'adresse attend sa confirmation ; sinon ne fait rien."""
    user = User.objects.filter(email=normalize_email_address(email)).first()
    if user and user.is_awaiting_confirmation:
        send_confirmation(request, user)


def confirm(user: User) -> None:
    """Confirme l'adresse du compte : le client peut désormais envoyer des demandes de voyage."""
    user.email_confirmed_at = timezone.now()
    user.save(update_fields=["email_confirmed_at"])


def purge_unconfirmed(now=None) -> int:
    """Supprime les comptes clients jamais confirmés (RGPD : pas de données sans raison)."""
    limit = (now or timezone.now()) - UNCONFIRMED_RETENTION
    _, deleted = User.objects.filter(
        role=Role.CLIENT, email_confirmed_at__isnull=True, date_joined__lt=limit
    ).delete()
    # Seuls les comptes sont comptés, pas leurs favoris supprimés avec eux.
    return deleted.get(User._meta.label, 0)


def notification_context(user: User, absolute_url: Callable[[str], str]) -> dict:
    """Variables communes aux e-mails d'inscription ; `absolute_url` rend un chemin absolu
    (request.build_absolute_uri pendant une requête, site_url hors requête)."""
    return {
        "user": user,
        "login_link": absolute_url(reverse("login")),
        "password_reset_link": absolute_url(reverse("password_reset")),
    }


def _notify(request, user: User, kind: EmailKind, template_name: str, extra: dict | None = None) -> bool:
    # Limite par adresse : on ne peut pas se servir du site pour inonder une boîte e-mail.
    if confirmation_emails.is_locked(user.email):
        return False
    confirmation_emails.record(user.email)
    context = {**notification_context(user, request.build_absolute_uri), **(extra or {})}
    return send_email(user.email, kind, template_name, context, user=user)

"""Inscription des clients avec confirmation de l'adresse e-mail.

Le parcours ne révèle jamais si une adresse est déjà inscrite :
- adresse nouvelle (ou inscription en attente) : compte inactif + lien de confirmation ;
- adresse déjà utilisée : aucun compte créé, la propriétaire est prévenue par e-mail.
Le mot de passe est choisi après le clic sur le lien : seule la personne qui reçoit
les e-mails de l'adresse peut l'activer (pas de « pré-détournement » de compte).
"""

from datetime import timedelta

from django.core import signing
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User, normalize_email_address
from accounts.services.emails import send_email
from accounts.services.throttling import confirmation_emails

CONFIRMATION_MAX_AGE = timedelta(hours=24)
UNCONFIRMED_RETENTION = timedelta(days=7)
_TOKEN_SALT = "accounts.sign-up-confirmation"
_PERSONAL_FIELDS = ("first_name", "last_name", "phone", "birth_date")


def make_confirmation_token(user: User) -> str:
    # L'adresse fait partie du jeton : un lien ne vaut que pour l'adresse qui l'a reçu.
    return signing.dumps({"id": user.pk, "email": user.email}, salt=_TOKEN_SALT)


def user_from_token(token: str) -> User | None:
    """Compte visé par le lien, ou None si le lien est faux, expiré ou ne correspond plus."""
    try:
        data = signing.loads(token, salt=_TOKEN_SALT, max_age=CONFIRMATION_MAX_AGE)
    except signing.BadSignature:  # comprend les liens expirés
        return None
    return User.objects.filter(pk=data.get("id"), email=data.get("email"), role=Role.CLIENT).first()


def request_sign_up(request, form) -> None:
    """Traite un formulaire d'inscription valide, sans révéler si l'adresse existe."""
    email = normalize_email_address(form.cleaned_data["email"])
    existing = User.objects.filter(email=email).first()
    if existing and not existing.is_awaiting_confirmation:
        _notify(
            request, existing, "Tentative d'inscription avec votre adresse", "accounts/emails/sign_up_existing.txt"
        )
        return

    # Nouvelle inscription, ou nouvelle tentative qui remplace une inscription en attente.
    user = existing or User(email=email, role=Role.CLIENT)
    for field in _PERSONAL_FIELDS:
        setattr(user, field, form.cleaned_data.get(field))
    user.is_active = False
    user.consent_date = timezone.now()
    user.date_joined = timezone.now()
    user.set_unusable_password()
    user.save()
    send_confirmation(request, user)


def send_confirmation(request, user: User) -> None:
    link = request.build_absolute_uri(reverse("confirm_sign_up", args=[make_confirmation_token(user)]))
    _notify(
        request,
        user,
        "Confirmez votre inscription",
        "accounts/emails/sign_up_confirmation.txt",
        {"confirmation_link": link},
    )


def resend_confirmation(request, email: str) -> None:
    """Renvoie le lien si une inscription est en attente pour cette adresse ; sinon ne fait rien."""
    user = User.objects.filter(email=normalize_email_address(email)).first()
    if user and user.is_awaiting_confirmation:
        send_confirmation(request, user)


def confirm(user: User) -> None:
    user.is_active = True
    user.email_confirmed_at = timezone.now()
    user.save(update_fields=["is_active", "email_confirmed_at", "password"])


def purge_unconfirmed(now=None) -> int:
    """Supprime les inscriptions jamais confirmées (RGPD : pas de données sans raison)."""
    limit = (now or timezone.now()) - UNCONFIRMED_RETENTION
    deleted, _ = User.objects.filter(
        role=Role.CLIENT, is_active=False, email_confirmed_at__isnull=True, date_joined__lt=limit
    ).delete()
    return deleted


def _notify(request, user: User, subject: str, template_name: str, extra: dict | None = None) -> None:
    # Limite par adresse : on ne peut pas se servir du site pour inonder une boîte e-mail.
    if confirmation_emails.is_locked(user.email):
        return
    confirmation_emails.record(user.email)
    context = {
        "user": user,
        "login_link": request.build_absolute_uri(reverse("login")),
        "password_reset_link": request.build_absolute_uri(reverse("password_reset")),
        **(extra or {}),
    }
    send_email(subject, template_name, context, user.email)

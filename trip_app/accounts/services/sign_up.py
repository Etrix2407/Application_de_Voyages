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

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core import signing
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from accounts.models import EmailKind, Role, User, normalize_email_address
from accounts.services.account_deletion import delete_account
from accounts.services.emails import send_email, site_url
from accounts.services.throttling import confirmation_emails

CONFIRMATION_MAX_AGE = timedelta(hours=48)
UNCONFIRMED_RETENTION = timedelta(days=30)
_TOKEN_SALT = "accounts.sign-up-confirmation"
_PERSONAL_FIELDS = ("first_name", "last_name", "phone", "birth_date")


def make_confirmation_token(user: User) -> str:
    # L'adresse fait partie du jeton : un lien ne vaut que pour l'adresse qui l'a reçu. Seule son
    # empreinte y figure : le jeton est signé mais lisible, l'adresse n'apparaît pas dans l'URL.
    # La date d'inscription aussi : un lien ne vaut que pour les données envoyées avec lui.
    return signing.dumps(
        {"id": user.pk, "address": _address_fingerprint(user.email), "joined": user.date_joined.isoformat()},
        salt=_TOKEN_SALT,
    )


def user_from_token(token: str) -> User | None:
    """Compte visé par le lien, ou None si le lien est faux, expiré ou ne correspond plus."""
    try:
        data = signing.loads(token, salt=_TOKEN_SALT, max_age=CONFIRMATION_MAX_AGE)
    except signing.BadSignature:  # comprend les liens expirés
        return None
    user = User.objects.filter(pk=data.get("id"), role=Role.CLIENT).first()
    if user is None or user.date_joined.isoformat() != data.get("joined"):
        return None
    if not constant_time_compare(str(data.get("address", "")), _address_fingerprint(user.email)):
        return None
    return user


def _address_fingerprint(email: str) -> str:
    return salted_hmac(_TOKEN_SALT, email).hexdigest()


def request_sign_up(data: dict) -> None:
    """Traite les données d'un formulaire d'inscription valide, sans révéler si l'adresse existe."""
    email = normalize_email_address(data["email"])
    existing = User.objects.filter(email=email).first()
    if existing and not existing.is_awaiting_confirmation:
        # Hachage sans usage : la réponse prend le même temps que pour une inscription nouvelle.
        make_password(data["password1"])
        _notify(existing, EmailKind.SIGN_UP_EXISTING, account_fields(existing))
        return

    user = User(email=email, role=Role.CLIENT, consent_date=timezone.now())
    for field in _PERSONAL_FIELDS:
        setattr(user, field, data.get(field))
    user.set_promotional_emails_consent(data.get("promotional_emails", False))
    user.set_password(data["password1"])
    try:
        with transaction.atomic():
            if existing:
                # Compte non confirmé : supprimé (sessions et favoris compris) et remplacé.
                # Ses anciens liens de confirmation ne valent plus rien (autre compte).
                existing.delete()
            user.save()
    except IntegrityError:
        # Inscription simultanée avec la même adresse : la première l'emporte. La page affichée
        # reste la même que pour une adresse déjà inscrite : rien n'est révélé.
        return
    send_confirmation(user)


def send_confirmation(user: User) -> bool:
    """Envoie le lien de confirmation. Renvoie False s'il n'est pas parti (limite ou panne)."""
    return _notify(user, EmailKind.SIGN_UP_CONFIRMATION, confirmation_fields(user))


def resend_confirmation(email: str) -> None:
    """Renvoie le lien si l'adresse attend sa confirmation ; sinon ne fait rien."""
    user = User.objects.filter(email=normalize_email_address(email)).first()
    if user and user.is_awaiting_confirmation:
        send_confirmation(user)


def confirm(user: User) -> None:
    """Confirme l'adresse du compte : le client peut désormais envoyer des demandes de voyage."""
    user.email_confirmed_at = timezone.now()
    user.save(update_fields=["email_confirmed_at"])


def purge_unconfirmed(now=None) -> int:
    """Supprime les comptes clients jamais confirmés (RGPD : pas de données sans raison)."""
    limit = (now or timezone.now()) - UNCONFIRMED_RETENTION
    accounts = User.objects.filter(role=Role.CLIENT, email_confirmed_at__isnull=True, date_joined__lt=limit)
    # Un par un : chaque titulaire reçoit un dernier e-mail (quelques comptes par jour au plus).
    deleted = 0
    for user in accounts:
        delete_account(user, EmailKind.UNCONFIRMED_ACCOUNT_DELETED)
        deleted += 1
    return deleted


def account_fields(user: User) -> dict:
    """Champs communs aux e-mails d'inscription : prénom, liens de connexion et « mot de passe oublié »."""
    return {
        "prénom": user.first_name,
        "lien de connexion": site_url(reverse("login")),
        "lien mot de passe oublié": site_url(reverse("password_reset")),
    }


def confirmation_fields(user: User) -> dict:
    """Champs de l'e-mail de confirmation, avec un lien neuf (valable CONFIRMATION_MAX_AGE)."""
    link = site_url(reverse("confirm_sign_up", args=[make_confirmation_token(user)]))
    return {**account_fields(user), "lien": link}


def _notify(user: User, kind: EmailKind, fields: dict) -> bool:
    # Limite par adresse : on ne peut pas se servir du site pour inonder une boîte e-mail.
    if confirmation_emails.is_locked(user.email):
        return False
    confirmation_emails.record(user.email)
    return send_email(user.email, kind, fields, user=user)

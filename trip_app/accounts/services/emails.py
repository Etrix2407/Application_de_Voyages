"""Envoi des e-mails du site (v5) : point d'entrée unique, utilisé par toutes les applications.

Chaque e-mail part en texte et en HTML (gabarit commun emails/base.html), après la validation
de la transaction en cours, et laisse une ligne dans le journal (EmailLog) sans son contenu.
Un échec d'envoi ne bloque jamais l'action de l'utilisateur : il est noté dans le journal.
"""

import logging
import smtplib
from collections.abc import Iterable, Mapping

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.db.transaction import on_commit
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone

from accounts.models import EmailFailure, EmailKind, EmailLog, EmailStatus, User
from accounts.services.email_texts import current_subject, render_email

logger = logging.getLogger(__name__)

# Après 3 tentatives, l'envoi passe à l'état « échec » (Recap 5).
MAX_ATTEMPTS = 3

def send_email(
    to: str,
    kind: EmailKind,
    fields: Mapping[str, object],
    *,
    user: User | None = None,
    order_number: int | None = None,
) -> bool:
    """Envoie un e-mail à `to` et l'inscrit au journal. À utiliser pour tout nouvel e-mail.

    - `kind` : type de l'e-mail (EmailKind) ; il fixe l'objet et le texte : celui de l'administrateur
      s'il l'a modifié, sinon le texte d'origine (voir email_texts.py). La version HTML est
      construite à partir de ce texte dans la mise en page commune.
    - `fields` : valeur de chaque champ variable du type (ex. {"prénom": ..., "lien": ...}).
      Les liens doivent être absolus (request.build_absolute_uri, ou site_url() hors d'une requête).
    - `user`, `order_number` : compte et demande de voyage concernés, notés dans le journal.

    L'envoi a lieu après la validation de la transaction en cours (immédiatement hors transaction).
    Renvoie False si l'envoi immédiat a échoué ; True s'il a réussi ou s'il aura lieu à la
    validation de la transaction. Ne lève jamais d'exception à cause de l'envoi lui-même.
    """
    subject, text = render_email(kind, fields)
    log = EmailLog.objects.create(
        recipient=to, kind=kind, subject=subject, user=user, order_number=order_number
    )
    message = build_message(to, subject, text)
    results = []
    on_commit(lambda: results.append(deliver(log, message)), robust=True)
    # Hors transaction, l'envoi vient d'avoir lieu ; sinon il aura lieu à la validation.
    return results[0] if results else True


def queue_emails(users: Iterable[User], kind: EmailKind, *, promotion_mailing_number: int | None = None) -> int:
    """Met en attente un e-mail par compte, sans l'envoyer : seules les lignes du journal sont créées.

    Pour les envois en nombre (jusqu'à 1 000 e-mails promotionnels) : les envoyer pendant la requête
    serait trop long. La commande planifiée process_emails les envoie à son prochain passage
    (voir retry_due_emails) ; le message est construit à ce moment par la reconstruction du type.
    Renvoie le nombre d'e-mails mis en attente.
    """
    subject = current_subject(kind)
    logs = [
        EmailLog(
            recipient=user.email,
            kind=kind,
            subject=subject,
            user=user,
            promotion_mailing_number=promotion_mailing_number,
        )
        for user in users
    ]
    return len(EmailLog.objects.bulk_create(logs, batch_size=500))


def build_message(to: str, subject: str, body: str, headers: dict[str, str] | None = None) -> EmailMultiAlternatives:
    """Message en texte et en HTML ; en mode test, il part à l'adresse de test.

    `headers` : en-têtes supplémentaires (ex. List-Unsubscribe des e-mails promotionnels).
    """
    if settings.EMAIL_TEST_MODE and settings.EMAIL_TEST_RECIPIENT:
        subject = f"[Test : {to}] {subject}"
        to = settings.EMAIL_TEST_RECIPIENT
    # Signature toujours présente ; les coordonnées de l'agence s'ajoutent dessous une fois réglées.
    signature = [f"L'équipe {settings.SITE_NAME}", *settings.EMAIL_SIGNATURE_LINES]
    text = f"{body.rstrip()}\n\n" + "\n".join(signature) + "\n"
    message = EmailMultiAlternatives(
        subject,
        text,
        to=[to],
        reply_to=[settings.EMAIL_REPLY_TO] if settings.EMAIL_REPLY_TO else None,
        headers=headers,
    )
    html = render_to_string(
        "emails/base.html",
        {
            "subject": subject,
            "body": body.strip(),
            "logo_url": _logo_url(),
            "site_name": settings.SITE_NAME,
            "signature": signature,
        },
    )
    message.attach_alternative(html, "text/html")
    return message


def deliver(log: EmailLog, message: EmailMultiAlternatives, connection: BaseEmailBackend | None = None) -> bool:
    """Tente l'envoi et note le résultat dans le journal. Renvoie True si le message est parti.

    `connection` : connexion déjà ouverte, partagée par tous les envois d'un même passage
    (voir retry_due_emails) ; sans elle, le message ouvre et ferme sa propre connexion.
    """
    log.attempts += 1
    log.last_attempt_at = timezone.now()
    if connection is not None:
        message.connection = connection
    try:
        message.send()
    except Exception as error:  # Toute erreur : un échec d'envoi ne doit jamais bloquer l'action.
        if connection is not None and not isinstance(error, smtplib.SMTPRecipientsRefused):
            _reopen(connection)
        log.last_error = (str(error) or type(error).__name__)[:500]
        log.failure = failure_of(error)
        # Ni adresse ni message d'erreur dans les logs (ils contiennent souvent l'adresse) : le
        # numéro de la ligne du journal suffit pour retrouver le détail.
        logger.error(
            "Échec de l'envoi de l'e-mail n° %s (%s) : %s", log.pk, type(error).__name__, log.get_failure_display()
        )
        log.status = EmailStatus.FAILED if log.attempts >= MAX_ATTEMPTS else EmailStatus.PENDING
        log.save(update_fields=["attempts", "last_attempt_at", "last_error", "failure", "status"])
        return False
    log.status = EmailStatus.SENT
    log.last_error = ""
    log.failure = ""
    log.save(update_fields=["attempts", "last_attempt_at", "last_error", "failure", "status"])
    return True


def _reopen(connection: BaseEmailBackend) -> None:
    # Après une erreur, la connexion peut être coupée : on repart d'une connexion neuve pour la suite.
    # Une adresse refusée ne la coupe pas (le serveur annule seulement ce message).
    connection.close()
    try:
        connection.open()
    except Exception:  # Serveur toujours injoignable : le message suivant retentera l'ouverture.
        pass


def failure_of(error: Exception) -> EmailFailure:
    """Type d'un échec d'envoi, pour le résumé affiché au personnel et « adresse à vérifier »."""
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        # Refus définitif (5xx) seulement : un refus temporaire (4xx) ne dit rien de l'adresse.
        codes = [code for code, _ in error.recipients.values()]
        if codes and all(code >= 500 for code in codes):
            return EmailFailure.RECIPIENT_REFUSED
        return EmailFailure.OTHER
    if isinstance(error, TimeoutError):
        return EmailFailure.TIMEOUT
    if isinstance(error, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return EmailFailure.UNREACHABLE
    if isinstance(error, smtplib.SMTPException):  # autre réponse du serveur (authentification...)
        return EmailFailure.OTHER
    if isinstance(error, OSError):  # connexion refusée, nom de serveur inconnu, réseau coupé...
        return EmailFailure.UNREACHABLE
    return EmailFailure.OTHER


def site_url(path: str) -> str:
    """Lien absolu vers une page du site, hors d'une requête (ex. site_url(reverse("login")))."""
    return f"{settings.SITE_URL}{path}"


def _logo_url() -> str:
    # URL absolue : rien à joindre au message, et l'image reste facultative (texte de remplacement).
    if not settings.EMAIL_LOGO_STATIC_PATH or not settings.SITE_URL:
        return ""
    return site_url(static(settings.EMAIL_LOGO_STATIC_PATH))

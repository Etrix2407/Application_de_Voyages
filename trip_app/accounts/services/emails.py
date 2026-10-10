"""Envoi des e-mails du site (v5) : point d'entrée unique, utilisé par toutes les applications.

Chaque e-mail part en texte et en HTML (gabarit commun emails/base.html), après la validation
de la transaction en cours, et laisse une ligne dans le journal (EmailLog) sans son contenu.
Un échec d'envoi ne bloque jamais l'action de l'utilisateur : il est noté dans le journal.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.transaction import on_commit
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus, User

logger = logging.getLogger(__name__)

# Après 3 tentatives, l'envoi passe à l'état « échec » (Recap 5).
MAX_ATTEMPTS = 3

# Objet de chaque type d'e-mail.
SUBJECTS = {
    EmailKind.SIGN_UP_CONFIRMATION: "Confirmez votre inscription",
    EmailKind.SIGN_UP_EXISTING: "Tentative d'inscription avec votre adresse",
    EmailKind.EMAIL_CHANGE_CONFIRMATION: "Confirmez votre nouvelle adresse e-mail",
    EmailKind.EMAIL_CHANGE_NOTICE: "Demande de changement de votre adresse e-mail",
    EmailKind.PASSWORD_RESET: "Changement de votre mot de passe",
    EmailKind.CLIENT_PASSWORD_LINK: "Changement de votre mot de passe",
    EmailKind.AGENT_ACTIVATION: "Activation de votre compte",
}


def send_email(
    to: str,
    kind: EmailKind,
    template_name: str,
    context: dict,
    *,
    user: User | None = None,
    order_number: int | None = None,
) -> bool:
    """Envoie un e-mail à `to` et l'inscrit au journal. À utiliser pour tout nouvel e-mail.

    - `kind` : type de l'e-mail (EmailKind) ; il fixe l'objet (SUBJECTS).
    - `template_name` : gabarit du texte, en texte brut, qui commence par {% autoescape off %} ;
      la version HTML est construite à partir de ce texte dans la mise en page commune.
    - `context` : variables du gabarit. Les liens doivent être absolus (request.build_absolute_uri,
      ou site_url() hors d'une requête).
    - `user`, `order_number` : compte et demande de voyage concernés, notés dans le journal.

    L'envoi a lieu après la validation de la transaction en cours (immédiatement hors transaction).
    Renvoie False si l'envoi immédiat a échoué ; True s'il a réussi ou s'il aura lieu à la
    validation de la transaction. Ne lève jamais d'exception à cause de l'envoi lui-même.
    """
    subject = SUBJECTS[kind]
    text = render_to_string(template_name, context)
    log = EmailLog.objects.create(
        recipient=to, kind=kind, subject=subject, user=user, order_number=order_number
    )
    message = build_message(to, subject, text)
    results = []
    on_commit(lambda: results.append(deliver(log, message)), robust=True)
    # Hors transaction, l'envoi vient d'avoir lieu ; sinon il aura lieu à la validation.
    return results[0] if results else True


def build_message(to: str, subject: str, body: str) -> EmailMultiAlternatives:
    """Message en texte et en HTML ; en mode test, il part à l'adresse de test."""
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


def deliver(log: EmailLog, message: EmailMultiAlternatives) -> bool:
    """Tente l'envoi et note le résultat dans le journal. Renvoie True si le message est parti."""
    log.attempts += 1
    log.last_attempt_at = timezone.now()
    try:
        message.send()
    except Exception as error:  # Toute erreur : un échec d'envoi ne doit jamais bloquer l'action.
        logger.exception("Échec de l'envoi de l'e-mail « %s » à %s", log.subject, log.recipient)
        log.last_error = (str(error) or type(error).__name__)[:500]
        log.status = EmailStatus.FAILED if log.attempts >= MAX_ATTEMPTS else EmailStatus.PENDING
        log.save(update_fields=["attempts", "last_attempt_at", "last_error", "status"])
        return False
    log.status = EmailStatus.SENT
    log.last_error = ""
    log.save(update_fields=["attempts", "last_attempt_at", "last_error", "status"])
    return True


def site_url(path: str) -> str:
    """Lien absolu vers une page du site, hors d'une requête (ex. site_url(reverse("login")))."""
    return f"{settings.SITE_URL}{path}"


def _logo_url() -> str:
    # URL absolue : rien à joindre au message, et l'image reste facultative (texte de remplacement).
    if not settings.EMAIL_LOGO_STATIC_PATH or not settings.SITE_URL:
        return ""
    return site_url(static(settings.EMAIL_LOGO_STATIC_PATH))

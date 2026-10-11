"""Nouvelles tentatives et renvoi manuel des e-mails (v5).

Le journal ne garde ni le contenu ni les liens de sécurité des messages : pour retenter un envoi,
le message est reconstruit à partir de son type, de son destinataire et du compte ou de la
demande liés, avec un lien de sécurité neuf. Chaque type d'e-mail déclare sa reconstruction :

    @rebuilder(OrderEmail.ORDER_PLACED)
    def _order_placed(log: EmailLog) -> RebuiltEmail | None: ...

Le module qui contient ces fonctions est importé dans le ready() de son application
(voir accounts/apps.py et accounts/services/email_rebuilders.py). Un type sans reconstruction
passe à l'état « échec » dès sa première tentative ratée.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple

from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.db.models import Case, Q, When
from django.utils import timezone

from accounts.models import EmailFailure, EmailLog, EmailStatus
from accounts.services.email_texts import current_text, render_email
from accounts.services.emails import build_message, deliver

logger = logging.getLogger(__name__)

# Délai minimal avant la tentative suivante, selon le nombre de tentatives déjà faites :
# 2e tentative au moins 5 minutes après la 1re, 3e au moins 15 minutes après la 2e.
RETRY_DELAYS = {1: timedelta(minutes=5), 2: timedelta(minutes=15)}
# Envoi jamais tenté (serveur arrêté juste après l'action) : repris au bout de 5 minutes.
NEVER_ATTEMPTED_DELAY = timedelta(minutes=5)
# Un passage envoie au plus 200 e-mails (le reste part aux passages suivants, toutes les 5 minutes)
# et ne prend plus de nouveau message après 20 minutes (serveur très lent ou injoignable).
EMAILS_PER_PASS = 200
MAX_PASS_DURATION = timedelta(minutes=20)

# Raisons affichées (last_error) ; l'état « non renvoyable » est porté par EmailLog.failure.
NOT_REBUILDABLE = "Ce type d'e-mail ne peut pas être renvoyé."
OBSOLETE = "Message devenu sans objet (compte supprimé ou modifié depuis) : il n'a pas été renvoyé."


class AlreadyResent(Exception):
    """L'e-mail n'est plus en échec : il vient d'être renvoyé par une autre requête."""


class RebuiltEmail(NamedTuple):
    """Valeurs des champs variables d'un message reconstruit (liens de sécurité neufs).

    `headers` : en-têtes supplémentaires, facultatifs (ex. List-Unsubscribe).
    """

    fields: dict
    headers: dict[str, str] | None = None


Rebuilder = Callable[[EmailLog], RebuiltEmail | None]
_REBUILDERS: dict[str, Rebuilder] = {}
# Types envoyés en nombre par queue_emails (ex. e-mails promotionnels), déclarés par rebuilder(queued=True).
_QUEUED_KINDS: set[str] = set()


class PassTexts(dict):
    """Objet et texte de chaque type (current_text), lus une seule fois par passage."""

    def __missing__(self, kind: str) -> tuple[str, str]:
        self[kind] = current_text(kind)
        return self[kind]


def rebuilder(kind: str, *, queued: bool = False) -> Callable[[Rebuilder], Rebuilder]:
    """Déclare la reconstruction d'un type d'e-mail. Elle renvoie None si le message n'a plus
    de raison d'être (compte supprimé, adresse changée, lien devenu inutile...).

    `queued` : type mis en attente par queue_emails, sans envoi immédiat ; son premier envoi a lieu
    au passage suivant de process_emails, après les autres e-mails (voir retry_due_emails).
    """

    def register(function: Rebuilder) -> Rebuilder:
        _REBUILDERS[kind] = function
        if queued:
            _QUEUED_KINDS.add(kind)
        return function

    return register


def retry_due_emails(now: datetime | None = None) -> int:
    """Retente les envois en attente dont le délai est écoulé. Renvoie le nombre de messages repris.

    Les e-mails mis en attente par queue_emails (types déclarés avec queued=True) partent sans délai :
    c'est leur premier envoi. Un message déjà pris par une autre reprise (date de tentative posée) n'est repris
    qu'au bout de 5 minutes : pas de doublon pendant un envoi en nombre.

    Tout le passage utilise une seule connexion au serveur d'envoi, fermée à la fin ; il traite au
    plus EMAILS_PER_PASS e-mails, les plus anciens d'abord. Le texte de chaque type n'est lu qu'une fois.
    """
    now = now or timezone.now()
    deadline = time.monotonic() + MAX_PASS_DURATION.total_seconds()
    never_taken = Q(attempts=0, last_attempt_at__isnull=True)
    queued = Q(kind__in=_QUEUED_KINDS)
    due = (
        (never_taken & (Q(created_at__lte=now - NEVER_ATTEMPTED_DELAY) | queued))
        | Q(attempts=0, last_attempt_at__lte=now - NEVER_ATTEMPTED_DELAY)
    )
    for attempts, delay in RETRY_DELAYS.items():
        due |= Q(attempts=attempts, last_attempt_at__lte=now - delay)
    # Les envois en nombre (promotions) passent après les autres e-mails : une nouvelle tentative
    # (demande de voyage, lien de mot de passe...) n'attend pas la fin d'un envoi à 1 000 clients.
    queued_last = Case(When(queued, then=1), default=0)
    logs = list(
        EmailLog.objects.filter(due, status=EmailStatus.PENDING)
        .select_related("user")
        .order_by(queued_last, "pk")[:EMAILS_PER_PASS]
    )
    if not logs:
        return 0  # rien à envoyer : pas de connexion au serveur
    retried = 0
    texts = PassTexts()
    connection = get_connection()
    try:
        connection.open()
    except Exception:  # Serveur injoignable : aucune tentative consommée, tout reste dû pour le passage suivant.
        logger.error("Connexion au serveur d'envoi impossible : passage reporté.")
        return 0
    try:
        for log in logs:
            if time.monotonic() > deadline:
                break
            if not _claim(log):
                continue
            retried += 1
            try:
                redeliver(log, connection=connection, texts=texts)
            except Exception:  # Un message en erreur ne doit pas empêcher la reprise des suivants.
                logger.exception("Impossible de reprendre l'e-mail n° %s", log.pk)
    finally:
        connection.close()
    return retried


def resend(log: EmailLog) -> bool:
    """Renvoi manuel d'un e-mail en échec : la même ligne du journal est remise en attente,
    avec un compteur de tentatives remis à zéro, et l'envoi est tenté tout de suite.

    En cas de nouvel échec, les tentatives automatiques reprennent (5 puis 15 minutes).
    Renvoie True si le message est parti. Lève AlreadyResent si la ligne n'est plus en échec
    (double clic, ou renvoi par un collègue au même moment) : rien n'est envoyé une 2e fois.
    """
    taken_at = timezone.now()
    # Prise conditionnelle : une seule requête peut faire passer la ligne de « échec » à « en attente ».
    # La date de tentative posée écarte aussi la ligne de la reprise automatique pendant l'envoi.
    taken = EmailLog.objects.filter(pk=log.pk, status=EmailStatus.FAILED).update(
        status=EmailStatus.PENDING, attempts=0, last_attempt_at=taken_at
    )
    if not taken:
        raise AlreadyResent
    log.status, log.attempts, log.last_attempt_at = EmailStatus.PENDING, 0, taken_at
    return redeliver(log)


def redeliver(
    log: EmailLog, *, connection: BaseEmailBackend | None = None, texts: PassTexts | None = None
) -> bool:
    """Reconstruit le message et tente l'envoi ; renvoie True s'il est parti.

    Si le message ne peut pas être reconstruit, la ligne passe à l'état « échec » avec la raison.
    Le texte est celui du moment (modifié entre-temps par l'administrateur, peut-être) : l'objet
    noté au journal est mis à jour s'il a changé. `connection` et `texts` : connexion et textes
    partagés par les envois d'un même passage (voir retry_due_emails).
    """
    rebuild = _REBUILDERS.get(log.kind)
    rebuilt = rebuild(log) if rebuild and log.recipient else None
    if rebuilt is None:
        log.status = EmailStatus.FAILED
        log.failure = EmailFailure.OBSOLETE if rebuild else EmailFailure.NOT_REBUILDABLE
        log.last_error = OBSOLETE if rebuild else NOT_REBUILDABLE
        log.save(update_fields=["status", "failure", "last_error"])
        return False
    current = (texts if texts is not None else PassTexts())[log.kind]
    subject, body, html = render_email(log.kind, rebuilt.fields, current)
    if subject != log.subject:
        log.subject = subject
        log.save(update_fields=["subject"])
    return deliver(log, build_message(log.recipient, subject, body, html, rebuilt.headers), connection)


def _claim(log: EmailLog) -> bool:
    # Si deux reprises tournent en même temps, une seule prend chaque message : pas de doublon.
    # L'heure réelle de la prise (et non celle du début du passage) : un passage long ne laisse
    # pas ses derniers messages repris par un autre avant 5 minutes pleines.
    return bool(
        EmailLog.objects.filter(
            pk=log.pk, status=EmailStatus.PENDING, attempts=log.attempts, last_attempt_at=log.last_attempt_at
        ).update(last_attempt_at=timezone.now())
    )

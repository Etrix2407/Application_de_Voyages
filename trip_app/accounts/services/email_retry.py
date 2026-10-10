"""Nouvelles tentatives et renvoi manuel des e-mails (v5).

Le journal ne garde ni le contenu ni les liens de sécurité des messages : pour retenter un envoi,
le message est reconstruit à partir de son type, de son destinataire et du compte ou de la
demande liés, avec un lien de sécurité neuf. Chaque type d'e-mail déclare sa reconstruction :

    @rebuilder(EmailKind.MON_TYPE)
    def _mon_type(log: EmailLog) -> RebuiltEmail | None: ...

Le module qui contient ces fonctions est importé dans le ready() de son application
(voir accounts/apps.py et accounts/services/email_rebuilders.py). Un type sans reconstruction
passe à l'état « échec » dès sa première tentative ratée.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple

from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.emails import build_message, deliver

logger = logging.getLogger(__name__)

# Délai minimal avant la tentative suivante, selon le nombre de tentatives déjà faites :
# 2e tentative au moins 5 minutes après la 1re, 3e au moins 15 minutes après la 2e.
RETRY_DELAYS = {1: timedelta(minutes=5), 2: timedelta(minutes=15)}
# Envoi jamais tenté (serveur arrêté juste après l'action) : repris au bout de 5 minutes.
NEVER_ATTEMPTED_DELAY = timedelta(minutes=5)

NOT_REBUILDABLE = "Ce type d'e-mail ne peut pas être renvoyé."
OBSOLETE = "Message devenu sans objet (compte supprimé ou modifié depuis) : il n'a pas été renvoyé."


class RebuiltEmail(NamedTuple):
    """Gabarit et variables d'un message reconstruit (liens de sécurité neufs)."""

    template_name: str
    context: dict


Rebuilder = Callable[[EmailLog], RebuiltEmail | None]
_REBUILDERS: dict[str, Rebuilder] = {}


def rebuilder(kind: EmailKind) -> Callable[[Rebuilder], Rebuilder]:
    """Déclare la reconstruction d'un type d'e-mail. Elle renvoie None si le message n'a plus
    de raison d'être (compte supprimé, adresse changée, lien devenu inutile...)."""

    def register(function: Rebuilder) -> Rebuilder:
        _REBUILDERS[kind] = function
        return function

    return register


def retry_due_emails(now: datetime | None = None) -> int:
    """Retente les envois en attente dont le délai est écoulé. Renvoie le nombre de messages repris."""
    now = now or timezone.now()
    due = Q(attempts=0, created_at__lte=now - NEVER_ATTEMPTED_DELAY)
    for attempts, delay in RETRY_DELAYS.items():
        due |= Q(attempts=attempts, last_attempt_at__lte=now - delay)
    retried = 0
    for log in EmailLog.objects.filter(due, status=EmailStatus.PENDING).select_related("user").order_by("pk"):
        if not _claim(log, now):
            continue
        retried += 1
        try:
            redeliver(log)
        except Exception:  # Un message en erreur ne doit pas empêcher la reprise des suivants.
            logger.exception("Impossible de reprendre l'e-mail n° %s", log.pk)
    return retried


def resend(log: EmailLog) -> bool:
    """Renvoi manuel d'un e-mail en échec : la même ligne du journal est remise en attente,
    avec un compteur de tentatives remis à zéro, et l'envoi est tenté tout de suite.

    En cas de nouvel échec, les tentatives automatiques reprennent (5 puis 15 minutes).
    Renvoie True si le message est parti.
    """
    log.status = EmailStatus.PENDING
    log.attempts = 0
    return redeliver(log)


def redeliver(log: EmailLog) -> bool:
    """Reconstruit le message et tente l'envoi ; renvoie True s'il est parti.

    Si le message ne peut pas être reconstruit, la ligne passe à l'état « échec » avec la raison.
    """
    rebuild = _REBUILDERS.get(log.kind)
    rebuilt = rebuild(log) if rebuild and log.recipient else None
    if rebuilt is None:
        log.status = EmailStatus.FAILED
        log.last_error = OBSOLETE if rebuild else NOT_REBUILDABLE
        log.save(update_fields=["status", "last_error"])
        return False
    body = render_to_string(rebuilt.template_name, rebuilt.context)
    return deliver(log, build_message(log.recipient, log.subject, body))


def _claim(log: EmailLog, now: datetime) -> bool:
    # Si deux reprises tournent en même temps, une seule prend chaque message : pas de doublon.
    return bool(
        EmailLog.objects.filter(
            pk=log.pk, status=EmailStatus.PENDING, attempts=log.attempts, last_attempt_at=log.last_attempt_at
        ).update(last_attempt_at=now)
    )

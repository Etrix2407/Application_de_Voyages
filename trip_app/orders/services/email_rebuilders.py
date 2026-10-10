"""Reconstruction des e-mails des demandes de voyage, pour les nouvelles tentatives et le renvoi manuel.

La demande est retrouvée par son numéro (noté au journal). Le message n'est reconstruit que s'il
a toujours une raison d'être : demande encore là, client non supprimé (et toujours celui du journal),
demande toujours dans l'état annoncé (ex. pas de « confirmée » pour une demande annulée depuis).
"""

from accounts.models import EmailKind, EmailLog
from accounts.services.email_retry import RebuiltEmail, rebuilder
from orders.models import Order, Status, StatusChange
from orders.services.emails import (
    CANCELLED_BY_AGENCY_TEMPLATE,
    CANCELLED_BY_CLIENT_TEMPLATE,
    CONFIRMED_TEMPLATE,
    NEW_ORDER_ALERT_TEMPLATE,
    PLACED_TEMPLATE,
    cancelled_by_agency_context,
    client_context,
    confirmed_context,
    new_order_alert_context,
    placed_context,
)


def _order_of(log: EmailLog, status: str) -> Order | None:
    """Demande liée, si elle appartient toujours au client du journal et a cet état."""
    if log.user is None or log.order_number is None:
        return None
    return Order.objects.filter(pk=log.order_number, client=log.user, status=status).first()


def _last_change(order: Order) -> StatusChange | None:
    """Dernier changement d'état : l'auteur de la confirmation ou de l'annulation."""
    return order.history.filter(status=order.status).last()


@rebuilder(EmailKind.ORDER_PLACED)
def _order_placed(log: EmailLog) -> RebuiltEmail | None:
    order = _order_of(log, Status.PENDING)
    return RebuiltEmail(PLACED_TEMPLATE, placed_context(order)) if order else None


@rebuilder(EmailKind.ORDER_CONFIRMED)
def _order_confirmed(log: EmailLog) -> RebuiltEmail | None:
    order = _order_of(log, Status.CONFIRMED)
    change = _last_change(order) if order else None
    if change is None:
        return None
    # Nom figé de l'agent dans l'historique (prénom et nom), même si son compte a été supprimé.
    return RebuiltEmail(CONFIRMED_TEMPLATE, confirmed_context(order, change.author_name))


@rebuilder(EmailKind.ORDER_CANCELLED_BY_CLIENT)
def _order_cancelled_by_client(log: EmailLog) -> RebuiltEmail | None:
    order = _order_of(log, Status.CANCELLED)
    change = _last_change(order) if order else None
    if change is None or not change.by_client:
        return None
    return RebuiltEmail(CANCELLED_BY_CLIENT_TEMPLATE, client_context(order))


@rebuilder(EmailKind.ORDER_CANCELLED_BY_AGENCY)
def _order_cancelled_by_agency(log: EmailLog) -> RebuiltEmail | None:
    order = _order_of(log, Status.CANCELLED)
    change = _last_change(order) if order else None
    if change is None or change.by_client:
        return None
    # Explication pour le client (champ reason) ; le motif interne n'est jamais repris.
    return RebuiltEmail(CANCELLED_BY_AGENCY_TEMPLATE, cancelled_by_agency_context(order, change.reason))


@rebuilder(EmailKind.NEW_ORDER_ALERT)
def _new_order_alert(log: EmailLog) -> RebuiltEmail | None:
    # Envoyée à l'adresse commune (pas de compte lié) : reconstruite à partir de la demande seule.
    if log.order_number is None:
        return None
    order = Order.objects.filter(pk=log.order_number, client__isnull=False, status=Status.PENDING).first()
    return RebuiltEmail(NEW_ORDER_ALERT_TEMPLATE, new_order_alert_context(order)) if order else None

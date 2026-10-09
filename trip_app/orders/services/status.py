"""Changements d'état des demandes de voyage, toujours inscrits dans l'historique."""

from django.db import transaction

from orders.models import Order, Status, StatusChange


class TransitionNotAllowed(Exception):
    """Le changement d'état demandé n'est pas permis dans l'état actuel."""


@transaction.atomic
def cancel_by_client(order: Order, reason: str = "") -> None:
    """Le client annule sa demande, uniquement tant qu'elle est « En attente »."""
    # Mise à jour conditionnelle : deux annulations simultanées ne peuvent pas passer.
    updated = Order.objects.filter(pk=order.pk, status=Status.PENDING).update(status=Status.CANCELLED)
    if not updated:
        raise TransitionNotAllowed("Seule une demande en attente peut être annulée par le client.")
    order.status = Status.CANCELLED
    StatusChange.objects.create(
        order=order,
        status=Status.CANCELLED,
        author=order.client,
        author_name=StatusChange.CLIENT_AUTHOR,
        reason=reason.strip(),
    )

"""Changements d'état des demandes de voyage, toujours inscrits dans l'historique.

| Action                | Depuis                    | Par                       | Motif       |
| --------------------- | ------------------------- | ------------------------- | ----------- |
| cancel_by_client      | En attente                | le client                 | facultatif  |
| confirm_by_staff      | En attente                | agent ou administrateur   | —           |
| cancel_by_staff       | En attente ou Confirmée   | agent ou administrateur   | obligatoire |
"""

from django.db import transaction

from orders.models import Order, Status, StatusChange


class TransitionNotAllowed(Exception):
    """Le changement d'état demandé n'est pas permis dans l'état actuel."""


def cancel_by_client(order: Order, reason: str = "") -> None:
    _change_status(
        order, {Status.PENDING}, Status.CANCELLED, order.client, StatusChange.CLIENT_AUTHOR, reason,
        "Seule une demande en attente peut être annulée par le client.",
    )


def confirm_by_staff(order: Order, staff_member) -> None:
    _change_status(
        order, {Status.PENDING}, Status.CONFIRMED, staff_member, staff_member.get_full_name(), "",
        "Seule une demande en attente peut être confirmée.",
    )


def cancel_by_staff(order: Order, staff_member, reason: str) -> None:
    if not reason.strip():
        raise ValueError("Le motif est obligatoire quand le personnel annule une demande.")
    _change_status(
        order, {Status.PENDING, Status.CONFIRMED}, Status.CANCELLED, staff_member, staff_member.get_full_name(),
        reason, "Cette demande est déjà annulée.",
    )


@transaction.atomic
def _change_status(order, allowed_from, new_status, author, author_name, reason, refusal) -> None:
    # Mise à jour conditionnelle : deux actions simultanées ne peuvent pas passer toutes les deux.
    updated = Order.objects.filter(pk=order.pk, status__in=allowed_from).update(status=new_status)
    if not updated:
        raise TransitionNotAllowed(refusal)
    order.status = new_status
    # Nom figé : l'historique reste lisible même si le compte de l'agent est supprimé ensuite.
    StatusChange.objects.create(
        order=order, status=new_status, author=author, author_name=author_name, reason=reason.strip()
    )

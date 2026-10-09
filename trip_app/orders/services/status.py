"""Changements d'état des demandes de voyage, toujours inscrits dans l'historique.

| Action                | Depuis                    | Par                       | Motif       |
| --------------------- | ------------------------- | ------------------------- | ----------- |
| cancel_by_client      | En attente                | le client                 | facultatif  |
| confirm_by_staff      | En attente                | agent ou administrateur   | — (prix)    |
| cancel_by_staff       | En attente ou Confirmée   | agent ou administrateur   | obligatoire |
| cancel_after_account_deletion | En attente        | automatique (« Client »)  | fixé        |
"""

from decimal import Decimal

from django.db import transaction

from orders.models import Order, Status, StatusChange
from orders.services.placing import price_at_current_rates


# États de départ permis pour chaque action : seule source de ces règles (services et pages).
CLIENT_CANCELLABLE = frozenset({Status.PENDING})
CONFIRMABLE = frozenset({Status.PENDING})
STAFF_CANCELLABLE = frozenset({Status.PENDING, Status.CONFIRMED})


class TransitionNotAllowed(Exception):
    """Le changement d'état demandé n'est pas permis dans l'état actuel."""


def client_can_cancel(order: Order) -> bool:
    return order.status in CLIENT_CANCELLABLE


def staff_can_confirm(order: Order) -> bool:
    return order.status in CONFIRMABLE


def staff_can_cancel(order: Order) -> bool:
    return order.status in STAFF_CANCELLABLE


def cancel_by_client(order: Order, reason: str = "") -> None:
    _change_status(
        order, CLIENT_CANCELLABLE, Status.CANCELLED, order.client, StatusChange.CLIENT_AUTHOR, reason,
        "Seule une demande en attente peut être annulée par le client.", by_client=True,
    )


def confirm_by_staff(order: Order, staff_member) -> None:
    """Confirme la demande au prix recalculé aux tarifs du jour.

    Si le prix a changé depuis la demande, l'historique l'indique (visible par le client).
    """
    price = price_at_current_rates(order)
    note = "" if price == order.estimated_price else (
        f"Prix recalculé aux tarifs du jour : {_euros(order.estimated_price)} → {_euros(price)}."
    )
    _change_status(
        order, CONFIRMABLE, Status.CONFIRMED, staff_member, staff_member.get_full_name(), note,
        "Seule une demande en attente peut être confirmée.", updates={"confirmed_price": price},
    )
    order.confirmed_price = price


def _euros(amount: Decimal) -> str:
    return f"{amount:.2f}".replace(".", ",") + " €"


def cancel_by_staff(order: Order, staff_member, reason: str) -> None:
    if not reason.strip():
        raise ValueError("Le motif est obligatoire quand le personnel annule une demande.")
    _change_status(
        order, STAFF_CANCELLABLE, Status.CANCELLED, staff_member, staff_member.get_full_name(),
        reason, "Cette demande est déjà annulée.",
    )


# Motif visible par le personnel : plus personne à rappeler pour cette demande.
ACCOUNT_DELETED_REASON = "Compte client supprimé : demande annulée automatiquement."


def cancel_after_account_deletion(order: Order) -> None:
    """Le client supprime son compte : sa demande en attente n'a plus à être traitée."""
    _change_status(
        order, CLIENT_CANCELLABLE, Status.CANCELLED, None, StatusChange.CLIENT_AUTHOR, ACCOUNT_DELETED_REASON,
        "Seule une demande en attente est annulée à la suppression du compte.", by_client=True,
    )


@transaction.atomic
def _change_status(
    order, allowed_from, new_status, author, author_name, reason, refusal, by_client=False, updates=None
) -> None:
    # Mise à jour conditionnelle : deux actions simultanées ne peuvent pas passer toutes les deux.
    updated = Order.objects.filter(pk=order.pk, status__in=allowed_from).update(
        status=new_status, **(updates or {})
    )
    if not updated:
        raise TransitionNotAllowed(refusal)
    order.status = new_status
    # Nom figé : l'historique reste lisible même si le compte de l'agent est supprimé ensuite.
    StatusChange.objects.create(
        order=order, status=new_status, author=author, author_name=author_name, reason=reason.strip(),
        by_client=by_client,
    )

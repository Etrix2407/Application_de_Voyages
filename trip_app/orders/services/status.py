"""Changements d'état des demandes de voyage, toujours inscrits dans l'historique.

| Action                | Depuis                    | Par                       | Motif       |
| --------------------- | ------------------------- | ------------------------- | ----------- |
| cancel_by_client      | En attente                | le client                 | facultatif  |
| confirm_by_staff      | En attente, départ à venir | agent ou administrateur  | — (prix)    |
| cancel_by_staff       | En attente ou Confirmée   | agent ou administrateur   | interne obligatoire, explication facultative |
| cancel_after_account_deletion | En attente        | automatique (« Client »)  | interne, fixé |

Le motif (champ reason) est visible par le client ; le motif interne, par le personnel seulement.
Le client est prévenu par e-mail de chaque action, sauf de l'annulation automatique (compte supprimé).
"""

from django.db import transaction
from django.utils import timezone

from common.text import euros
from orders.models import Order, Status, StatusChange
from orders.services.emails import send_order_cancelled_by_agency, send_order_cancelled_by_client, send_order_confirmed
from orders.services.placing import price_at_current_rates


# États de départ permis pour chaque action : seule source de ces règles (services et pages).
CLIENT_CANCELLABLE = frozenset({Status.PENDING})
CONFIRMABLE = frozenset({Status.PENDING})
STAFF_CANCELLABLE = frozenset({Status.PENDING, Status.CONFIRMED})


class TransitionNotAllowed(Exception):
    """Le changement d'état demandé n'est pas permis dans l'état actuel."""


def client_can_cancel(order: Order) -> bool:
    return order.status in CLIENT_CANCELLABLE


def departure_passed(order: Order) -> bool:
    return order.departure_date < timezone.localdate()


def staff_can_confirm(order: Order) -> bool:
    # Décision de la cliente : une demande dont le départ est passé ne se confirme plus.
    return order.status in CONFIRMABLE and not departure_passed(order)


def staff_can_cancel(order: Order) -> bool:
    return order.status in STAFF_CANCELLABLE


def cancel_by_client(order: Order, reason: str = "") -> None:
    _change_status(
        order, CLIENT_CANCELLABLE, Status.CANCELLED, order.client, StatusChange.CLIENT_AUTHOR, reason,
        "Seule une demande en attente peut être annulée par le client.", by_client=True,
    )
    send_order_cancelled_by_client(order)


def confirm_by_staff(order: Order, staff_member) -> None:
    """Confirme la demande au prix recalculé aux tarifs du jour.

    Si le prix a changé depuis la demande, l'historique l'indique (visible par le client).
    """
    if departure_passed(order):
        raise TransitionNotAllowed("La date de départ est passée : cette demande ne peut plus être confirmée.")
    quote = price_at_current_rates(order)
    note = "" if quote.price == order.estimated_price else (
        f"Prix recalculé aux tarifs du jour : {euros(order.estimated_price)} → {euros(quote.price)}."
    )
    updates = {
        "confirmed_price": quote.price,
        "confirmed_discount": quote.discount,
        # Destination déjà chargée par le recalcul : c'est le prix du séjour réellement compté.
        "confirmed_destination_price": order.destination.price_from,
        "has_confirmed_destination_price": True,
    }
    _change_status(
        order, CONFIRMABLE, Status.CONFIRMED, staff_member, staff_member.get_full_name(), note,
        "Seule une demande en attente peut être confirmée.", updates=updates,
    )
    for field, value in updates.items():
        setattr(order, field, value)
    send_order_confirmed(order, staff_member)


def cancel_by_staff(order: Order, staff_member, internal_reason: str, explanation: str = "") -> None:
    """Annulation par l'agence : motif interne obligatoire, explication pour le client facultative.

    Le motif interne n'est montré qu'au personnel ; l'explication apparaît dans l'historique du client.
    """
    if not internal_reason.strip():
        raise ValueError("Le motif interne est obligatoire quand le personnel annule une demande.")
    _change_status(
        order, STAFF_CANCELLABLE, Status.CANCELLED, staff_member, staff_member.get_full_name(),
        explanation, "Cette demande est déjà annulée.", internal_reason=internal_reason,
    )
    send_order_cancelled_by_agency(order, explanation)


# Motif interne (personnel) : plus personne à rappeler pour cette demande.
ACCOUNT_DELETED_REASON = "Compte client supprimé : demande annulée automatiquement."


def cancel_after_account_deletion(order: Order) -> None:
    """Le client supprime son compte : sa demande en attente n'a plus à être traitée."""
    _change_status(
        order, CLIENT_CANCELLABLE, Status.CANCELLED, None, StatusChange.CLIENT_AUTHOR, "",
        "Seule une demande en attente est annulée à la suppression du compte.", by_client=True,
        internal_reason=ACCOUNT_DELETED_REASON,
    )


@transaction.atomic
def _change_status(
    order, allowed_from, new_status, author, author_name, reason, refusal, by_client=False, updates=None,
    internal_reason="",
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
        internal_reason=internal_reason.strip(), by_client=by_client,
    )

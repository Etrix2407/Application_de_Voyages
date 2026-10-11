"""Changements d'état des demandes de voyage, toujours inscrits dans l'historique.

| Action                | Depuis                    | Par                       | Motif       |
| --------------------- | ------------------------- | ------------------------- | ----------- |
| cancel_by_client      | En attente                | le client                 | facultatif  |
| confirm_by_staff      | En attente, départ à venir | agent ou administrateur  | — (prix)    |
| cancel_by_staff       | En attente ou Confirmée   | agent ou administrateur   | interne obligatoire, explication facultative |
| cancel_after_account_deletion | En attente        | automatique (« Client »)  | interne, fixé |

Le motif (champ reason) est visible par le client. Le motif interne n'apparaît ni sur le site ni dans
les e-mails du client, mais figure dans les données qu'il peut télécharger.
Le client est prévenu par e-mail de chaque action, sauf de l'annulation automatique (compte supprimé).
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from common.text import euros
from orders.models import Order, OrderStatus, StatusChange
from orders.services.emails import send_order_cancelled_by_agency, send_order_cancelled_by_client, send_order_confirmed
from orders.services.placing import price_at_current_rates
from orders.services.reminders import send_departure_reminders


# États de départ permis pour chaque action : seule source de ces règles (services et pages).
CLIENT_CANCELLABLE = frozenset({OrderStatus.PENDING})
CONFIRMABLE = frozenset({OrderStatus.PENDING})
STAFF_CANCELLABLE = frozenset({OrderStatus.PENDING, OrderStatus.CONFIRMED})
CONFIRM_REFUSAL = "Seule une demande en attente peut être confirmée."


class TransitionNotAllowed(Exception):
    """Le changement d'état demandé n'est pas permis dans l'état actuel."""


class PriceChanged(Exception):
    """Le prix aux tarifs du jour n'est plus celui que l'agent a vu en confirmant."""

    def __init__(self):
        super().__init__(
            "Le prix aux tarifs du jour a changé depuis l'affichage de la page : "
            "vérifiez le nouveau prix avant de confirmer."
        )


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
        order, OrderStatus.CANCELLED,
        allowed_from=CLIENT_CANCELLABLE,
        author=order.client,
        author_name=StatusChange.CLIENT_AUTHOR,
        reason=reason,
        refusal="Seule une demande en attente peut être annulée par le client.",
        by_client=True,
    )
    send_order_cancelled_by_client(order)


def confirm_by_staff(order: Order, staff_member, expected_price: Decimal | None = None) -> None:
    """Confirme la demande au prix recalculé aux tarifs du jour.

    Si le prix a changé depuis la demande, l'historique l'indique (visible par le client).
    `expected_price` : prix affiché à l'agent ; s'il ne correspond plus au recalcul, lève PriceChanged.
    """
    if order.status not in CONFIRMABLE:
        # Contrôle rapide avant le recalcul ; la mise à jour conditionnelle reste la garantie.
        raise TransitionNotAllowed(CONFIRM_REFUSAL)
    if departure_passed(order):
        raise TransitionNotAllowed("La date de départ est passée : cette demande ne peut plus être confirmée.")
    quote = price_at_current_rates(order)
    if expected_price is not None and expected_price != quote.price:
        raise PriceChanged
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
        order, OrderStatus.CONFIRMED,
        allowed_from=CONFIRMABLE,
        author=staff_member,
        author_name=staff_member.get_full_name(),
        reason=note,
        refusal=CONFIRM_REFUSAL,
        updates=updates,
    )
    for field, value in updates.items():
        setattr(order, field, value)
    send_order_confirmed(order, staff_member)
    # Départ dans 7 jours ou moins : le rappel part dès la confirmation (sinon, la commande quotidienne).
    send_departure_reminders(order_pk=order.pk)


def cancel_by_staff(order: Order, staff_member, internal_reason: str, explanation: str = "") -> None:
    """Annulation par l'agence : motif interne obligatoire, explication pour le client facultative.

    Le motif interne n'apparaît ni sur le site ni dans les e-mails du client, mais figure dans les données
    qu'il peut télécharger ; l'explication apparaît dans l'historique du client.
    """
    if not internal_reason.strip():
        raise ValueError("Le motif interne est obligatoire quand le personnel annule une demande.")
    _change_status(
        order, OrderStatus.CANCELLED,
        allowed_from=STAFF_CANCELLABLE,
        author=staff_member,
        author_name=staff_member.get_full_name(),
        reason=explanation,
        refusal="Cette demande est déjà annulée.",
        internal_reason=internal_reason,
    )
    send_order_cancelled_by_agency(order, explanation)


# Motif interne (personnel) : plus personne à rappeler pour cette demande.
ACCOUNT_DELETED_REASON = "Compte client supprimé : demande annulée automatiquement."


def cancel_after_account_deletion(order: Order) -> None:
    """Le client supprime son compte : sa demande en attente n'a plus à être traitée."""
    _change_status(
        order, OrderStatus.CANCELLED,
        allowed_from=CLIENT_CANCELLABLE,
        author=None,
        author_name=StatusChange.CLIENT_AUTHOR,
        refusal="Seule une demande en attente est annulée à la suppression du compte.",
        by_client=True,
        internal_reason=ACCOUNT_DELETED_REASON,
    )


@transaction.atomic
def _change_status(
    order: Order,
    new_status: str,
    *,
    allowed_from: frozenset,
    author,
    author_name: str,
    refusal: str,
    reason: str = "",
    internal_reason: str = "",
    by_client: bool = False,
    updates: dict | None = None,
) -> None:
    """Passe la demande à `new_status` si son état est dans `allowed_from`, sinon lève TransitionNotAllowed(refusal).

    `reason` est visible par le client ; `internal_reason` ne l'est pas sur le site (voir en tête).
    """
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

"""E-mails des demandes de voyage (v5) : au client à chaque étape, et l'alerte au personnel.

Tous passent par accounts.services.emails.send_email, avec le numéro de la demande pour le journal.
Le motif interne d'une annulation n'apparaît jamais dans un e-mail au client.
Une demande dont le client a supprimé son compte n'a plus de destinataire : aucun e-mail client.
Les fonctions *_context donnent la valeur des champs variables de chaque e-mail (voir
accounts/services/email_texts.py) ; elles servent aussi à reconstruire un message pour une
nouvelle tentative (voir orders/services/email_rebuilders.py).
"""

from django.conf import settings
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.text import capfirst

from accounts.models import EmailKind
from accounts.services.emails import send_email, site_url
from common.text import euros
from orders.models import Order

QUOTE_NOTE = "Le prix de la destination sera donné sur devis par votre conseiller."


def send_order_placed(order: Order) -> None:
    """Accusé de réception au client, avec le récapitulatif et le prix estimé."""
    _send_to_client(order, EmailKind.ORDER_PLACED, placed_context(order))


def send_order_confirmed(order: Order, staff_member) -> None:
    """Confirmation au client : récapitulatif au prix confirmé et nom du conseiller."""
    _send_to_client(order, EmailKind.ORDER_CONFIRMED, confirmed_context(order, staff_member.get_full_name()))


def send_order_cancelled_by_client(order: Order) -> None:
    """Accusé de réception de l'annulation faite par le client."""
    _send_to_client(order, EmailKind.ORDER_CANCELLED_BY_CLIENT, client_context(order))


def send_order_cancelled_by_agency(order: Order, explanation: str) -> None:
    """Annulation par l'agence : l'explication pour le client, s'il y en a une, et un mot d'excuse."""
    _send_to_client(order, EmailKind.ORDER_CANCELLED_BY_AGENCY, cancelled_by_agency_context(order, explanation))


def send_new_order_alert(order: Order) -> None:
    """Alerte à l'adresse commune du personnel, sans le téléphone ni l'e-mail du client."""
    send_email(
        settings.RESERVATIONS_EMAIL, EmailKind.NEW_ORDER_ALERT, new_order_alert_context(order), order_number=order.pk
    )


def client_context(order: Order) -> dict:
    """Champs communs aux e-mails du client (la demande doit avoir un client)."""
    return {
        "prénom": order.client.first_name,
        "numéro": order.pk,
        "destination": order.destination_label,
        "dates": order_dates(order),
    }


def placed_context(order: Order) -> dict:
    return {**client_context(order), "récapitulatif": _lines(_summary(order) + _estimated_price_lines(order))}


def confirmed_context(order: Order, advisor: str) -> dict:
    """`advisor` : prénom et nom de l'agent qui a confirmé."""
    summary = _lines(_summary(order) + _confirmed_price_lines(order))
    return {**client_context(order), "récapitulatif": summary, "conseiller": advisor}


def cancelled_by_agency_context(order: Order, explanation: str) -> dict:
    """`explanation` : explication pour le client (jamais le motif interne) ; vide = ligne omise."""
    explanation = explanation.strip()
    line = f"Explication de l'agence : {explanation}" if explanation else ""
    return {**client_context(order), "explication": line}


def new_order_alert_context(order: Order) -> dict:
    return {
        "numéro": order.pk,
        "destination": order.destination_label,
        "dates": capfirst(order_dates(order)),
        "client": order.client.get_full_name(),
        "lien": site_url(reverse("manage_order_detail", args=[order.pk])),
    }


def order_dates(order: Order) -> str:
    """Dates du voyage : « du 3 mai 2026 au 13 mai 2026 »."""
    return f"du {date_format(order.departure_date, 'j F Y')} au {date_format(order.return_date, 'j F Y')}"


def _send_to_client(order: Order, kind: EmailKind, fields: dict) -> None:
    client = order.client
    if client is None:
        return
    send_email(client.email, kind, fields, user=client, order_number=order.pk)


def _lines(summary: list[tuple[str, str]]) -> str:
    """Une ligne « - libellé : valeur » par information."""
    return "\n".join(f"- {label} : {value}" for label, value in summary)


def _summary(order: Order) -> list[tuple[str, str]]:
    """Lignes « libellé : valeur » communes aux e-mails du client (hors prix)."""
    travellers = f"{order.adults} adulte{'s' if order.adults > 1 else ''}"
    if order.children:
        travellers += f", {order.children} enfant{'s' if order.children > 1 else ''}"
    activities = [line.activity_name for line in order.activities.all()]
    return [
        ("N° de demande", str(order.pk)),
        ("Destination", order.destination_label),
        ("Dates", order_dates(order).capitalize()),
        ("Voyageurs", travellers),
        ("Activités", ", ".join(activities) or "Aucune"),
    ]


def _estimated_price_lines(order: Order) -> list[tuple[str, str]]:
    lines = []
    if order.promotion_name:
        lines += [
            ("Prix avant remise", euros(order.price_before_discount)),
            ("Promotion", f"{order.promotion_name} (-{euros(order.discount)})"),
        ]
    price = f"{euros(order.estimated_price)} (estimation, non contractuelle)"
    if order.is_quote_required:
        price += f". {QUOTE_NOTE}"
    return lines + [("Prix estimé", price)]


def _confirmed_price_lines(order: Order) -> list[tuple[str, str]]:
    # Comme sur le site : remise ré-appliquée au prix recalculé, ou « non applicable » (0 €).
    lines = []
    if order.promotion_name and order.confirmed_discount_applies:
        lines += [
            ("Prix avant remise", euros(order.confirmed_price_before_discount)),
            ("Promotion", f"{order.promotion_name} (-{euros(order.confirmed_discount)})"),
        ]
    elif order.promotion_name:
        lines.append(("Promotion", f"{order.promotion_name} (remise non applicable au prix recalculé)"))
    price = f"{euros(order.confirmed_price)} (recalculé aux tarifs du jour de la confirmation, non contractuel)"
    if order.is_confirmed_quote_required:
        price += f". {QUOTE_NOTE}"
    return lines + [("Prix confirmé", price)]

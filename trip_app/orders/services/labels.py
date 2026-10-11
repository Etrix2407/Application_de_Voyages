"""Libellés d'une demande de voyage, communs à tous les e-mails."""

from orders.models import Order


def destination_label(order: Order) -> str:
    """Destination et pays figés sur la demande : « Kyoto (Japon) »."""
    return f"{order.destination_name} ({order.country_name})"

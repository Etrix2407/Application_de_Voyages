"""RGPD (portabilité) : demandes de voyage d'un client, prêtes à être exportées.

Le client y retrouve ce qu'il voit dans « Mes demandes » : noms et prix figés,
promotion appliquée, historique avec « Agence » à la place du nom de l'agent.
Droit d'accès : le motif interne de l'agence, absent du site, est inclus dans l'export.
Le jeton d'envoi (donnée technique interne) n'est pas exporté.
"""

from orders.models import Order


def orders_data(client) -> list[dict]:
    orders = Order.objects.filter(client=client).prefetch_related("activities", "history")
    return [_order_data(order) for order in orders]


def _order_data(order: Order) -> dict:
    return {
        "id": order.pk,
        "created_at": order.created_at,
        "status": order.get_status_display(),
        "destination": order.destination_name,
        "country": order.country_name,
        "departure_date": order.departure_date,
        "return_date": order.return_date,
        "adults": order.adults,
        "children": order.children,
        "remarks": order.remarks,
        "activities": [
            {"name": line.activity_name, "unit_price": line.unit_price} for line in order.activities.all()
        ],
        "destination_price": order.destination_price,
        "estimated_price": order.estimated_price,
        "confirmed_price": order.confirmed_price,
        "promotion": order.promotion_name,
        "discount": order.discount,
        "confirmed_discount": order.confirmed_discount,
        "history": [
            {
                "changed_at": change.changed_at,
                "status": change.get_status_display(),
                "by": change.author_for_client,
                "reason": change.reason,
                "internal_reason": change.internal_reason,
            }
            for change in order.history.all()
        ],
    }

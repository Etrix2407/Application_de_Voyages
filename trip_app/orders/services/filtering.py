"""Filtrage et tri des demandes de voyage pour le personnel."""

from common.text import normalize
from orders.models import Order

NEWEST_FIRST = "recent"
OLDEST_FIRST = "ancien"


def filter_orders(criteria: dict):
    """Renvoie les demandes correspondant aux critères (formulaire validé), triées par date de demande."""
    # Remarques non affichées dans la liste : inutile de charger jusqu'à 2 000 caractères par ligne.
    orders = Order.objects.select_related("client", "destination__country").defer("remarks")
    if criteria.get("status"):
        orders = orders.filter(status=criteria["status"])
    if criteria.get("country"):
        orders = orders.filter(destination__country=criteria["country"])
    if criteria.get("destination"):
        orders = orders.filter(destination=criteria["destination"])
    if criteria.get("departure_from"):
        orders = orders.filter(departure_date__gte=criteria["departure_from"])
    if criteria.get("departure_to"):
        orders = orders.filter(departure_date__lte=criteria["departure_to"])
    # Le numéro départage les demandes créées au même instant : l'ordre ne change jamais d'une page à l'autre.
    if criteria.get("sort") == OLDEST_FIRST:
        orders = orders.order_by("created_at", "pk")
    else:
        orders = orders.order_by("-created_at", "-pk")

    words = normalize(criteria.get("client") or "").split()
    if words:
        # Filtre en Python : SQLite ne sait pas ignorer les accents.
        orders = [order for order in orders if order.client and _matches(order.client, words)]
    return orders


def _matches(client, words: list[str]) -> bool:
    text = normalize(f"{client.last_name} {client.first_name} {client.email}")
    return all(word in text for word in words)

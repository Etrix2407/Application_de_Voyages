"""Filtrage et tri des demandes de voyage pour le personnel."""

from accounts.models import Role, User
from accounts.services.client_search import client_matches, search_words
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

    words = search_words(criteria.get("client"))
    if words:
        # Les clients (nombre borné) sont cherchés en Python, sans accents ; les demandes, qui
        # s'accumulent, restent filtrées et paginées par la base. Une demande anonymisée est exclue.
        matching = [client.pk for client in User.objects.filter(role=Role.CLIENT) if client_matches(client, words)]
        orders = orders.filter(client_id__in=matching)
    return orders

"""Création d'une demande de voyage par un client."""

from decimal import Decimal

from django.db import transaction

from catalog.models import Destination
from orders.models import Order, OrderActivity, Status, StatusChange
from orders.services.pricing import estimate_price


def estimate_for(destination: Destination, activities, adults: int, children: int) -> Decimal:
    return estimate_price(
        destination.price_from, [activity.price_per_person for activity in activities], adults, children
    )


def find_pending_duplicates(client, destination: Destination, departure_date, return_date):
    """Demandes « En attente » du client pour la même destination aux mêmes dates."""
    return Order.objects.filter(
        client=client,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        status=Status.PENDING,
    )


@transaction.atomic
def place_order(client, destination: Destination, data: dict) -> Order:
    """Enregistre la demande « En attente » avec ses prix figés et son historique.

    `data` provient d'un formulaire validé (dates, voyageurs, activités, remarques).
    """
    activities = list(data["activities"])
    order = Order.objects.create(
        client=client,
        destination=destination,
        departure_date=data["departure_date"],
        return_date=data["return_date"],
        adults=data["adults"],
        children=data["children"],
        remarks=data["remarks"],
        destination_price=destination.price_from,
        estimated_price=estimate_for(destination, activities, data["adults"], data["children"]),
    )
    OrderActivity.objects.bulk_create(
        OrderActivity(order=order, activity=activity, unit_price=activity.price_per_person)
        for activity in activities
    )
    StatusChange.objects.create(order=order, status=Status.PENDING, author=client, author_name=StatusChange.CLIENT_AUTHOR)
    return order

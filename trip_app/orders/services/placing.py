"""Création d'une demande de voyage par un client."""

from decimal import Decimal

from django.db import IntegrityError, transaction

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


class AlreadySubmitted(Exception):
    """La même page de vérification a déjà été envoyée (double clic)."""

    def __init__(self, order: Order):
        super().__init__("Cette demande a déjà été envoyée.")
        self.order = order


def place_order(client, destination: Destination, data: dict, submission_token=None) -> Order:
    """Enregistre la demande « En attente » avec ses prix figés et son historique.

    `data` provient d'un formulaire validé (dates, voyageurs, activités, remarques).
    Un `submission_token` déjà utilisé lève AlreadySubmitted : la base garantit l'unicité,
    même si deux envois arrivent au même instant.
    """
    try:
        return _create_order(client, destination, data, submission_token)
    except IntegrityError:
        existing = Order.objects.filter(submission_token=submission_token).first() if submission_token else None
        if existing is None:
            raise
        raise AlreadySubmitted(existing) from None


@transaction.atomic
def _create_order(client, destination: Destination, data: dict, submission_token) -> Order:
    activities = list(data["activities"])
    order = Order.objects.create(
        submission_token=submission_token,
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

"""Création de demandes de voyage pour les tests."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from orders.models import MIN_DAYS_BEFORE_DEPARTURE, Order, OrderActivity


def departure_in(days: int = MIN_DAYS_BEFORE_DEPARTURE + 30):
    return timezone.localdate() + timedelta(days=days)


def create_order(client, destination, activities=(), **fields) -> Order:
    fields.setdefault("departure_date", departure_in())
    fields.setdefault("return_date", fields["departure_date"] + timedelta(days=10))
    fields.setdefault("adults", 2)
    fields.setdefault("destination_price", destination.price_from)
    fields.setdefault("estimated_price", Decimal("0"))
    order = Order.objects.create(client=client, destination=destination, **fields)
    for activity in activities:
        OrderActivity.objects.create(order=order, activity=activity, unit_price=activity.price_per_person)
    return order

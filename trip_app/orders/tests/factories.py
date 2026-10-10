"""Création de demandes de voyage pour les tests."""

import re
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from orders.models import MIN_DAYS_BEFORE_DEPARTURE, Order, OrderActivity, client_fingerprint


def departure_in(days: int = MIN_DAYS_BEFORE_DEPARTURE + 30):
    return timezone.localdate() + timedelta(days=days)


def create_order(client, destination, activities=(), **fields) -> Order:
    fields.setdefault("departure_date", departure_in())
    fields.setdefault("return_date", fields["departure_date"] + timedelta(days=10))
    fields.setdefault("adults", 2)
    fields.setdefault("destination_price", destination.price_from)
    fields.setdefault("estimated_price", Decimal("0"))
    fields.setdefault("destination_name", destination.name)
    fields.setdefault("country_name", destination.country.name)
    if client is not None:
        fields.setdefault("client_fingerprint", client_fingerprint(client.email))
    order = Order.objects.create(client=client, destination=destination, **fields)
    for activity in activities:
        OrderActivity.objects.create(
            order=order, activity=activity, activity_name=activity.name, unit_price=activity.price_per_person
        )
    return order


def review_tokens(review_response) -> dict:
    """Champs cachés de la page de vérification : prix affiché et jeton d'envoi."""
    page = review_response.content.decode()
    return {
        name: re.search(rf'name="{name}" value="([^"]*)"', page).group(1)
        for name in ("expected_price", "submission_token")
    }


def submit_order(test_client, url: str, data: dict, follow: bool = False):
    """Parcours réel : page de vérification, puis « Envoyer ma demande » avec ses champs cachés."""
    review = test_client.post(url, data)
    return test_client.post(url, {**data, **review_tokens(review), "confirm": ""}, follow=follow)

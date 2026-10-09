"""Création d'avis pour les tests."""

from datetime import timedelta

from django.utils import timezone

from orders.models import Order, Status
from orders.tests.factories import create_order
from reviews.models import Review


def create_trip_done(client, destination, **fields) -> Order:
    """Demande confirmée dont le voyage est terminé : elle peut recevoir un avis."""
    today = timezone.localdate()
    fields.setdefault("departure_date", today - timedelta(days=20))
    fields.setdefault("return_date", today - timedelta(days=10))
    # Dates passées : créées directement, sans les règles d'une nouvelle demande.
    fields.setdefault("status", Status.CONFIRMED)
    return create_order(client, destination, **fields)


def create_review(order: Order, **fields) -> Review:
    fields.setdefault("rating", 5)
    fields.setdefault("title", "Séjour inoubliable")
    fields.setdefault("comment", "Tout était parfait.")
    return Review.objects.create(order=order, **fields)

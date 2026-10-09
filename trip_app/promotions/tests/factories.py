"""Création de promotions pour les tests."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from promotions.models import Kind, Promotion


def create_promotion(countries=(), destinations=(), **fields) -> Promotion:
    """Par défaut : -10 % sur tout le catalogue, automatique, en cours pendant 30 jours."""
    today = timezone.localdate()
    fields.setdefault("name", "Semaine du Portugal")
    fields.setdefault("kind", Kind.PERCENT)
    fields.setdefault("value", Decimal("10"))
    fields.setdefault("starts_on", today)
    fields.setdefault("ends_on", today + timedelta(days=30))
    promotion = Promotion.objects.create(**fields)
    promotion.countries.set(countries)
    promotion.destinations.set(destinations)
    return promotion

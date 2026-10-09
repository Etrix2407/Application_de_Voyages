"""Notes publiques des destinations : moyenne et nombre d'avis publiés.

Seuls les avis publiés, sur une destination encore proposée, comptent
(« Pas encore d'avis » plutôt que « 0 étoile »).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count

from reviews.models import MAX_RATING, Review

# Tri des avis d'une destination : clé dans l'URL -> ordre.
NEWEST_FIRST = "recents"
BEST_FIRST = "meilleures-notes"
REVIEW_ORDERS = {
    NEWEST_FIRST: ("-published_at", "-pk"),
    BEST_FIRST: ("-rating", "-published_at", "-pk"),
}


@dataclass(frozen=True)
class RatingSummary:
    average: Decimal | None
    count: int

    @property
    def has_reviews(self) -> bool:
        return self.count > 0


NO_REVIEWS = RatingSummary(average=None, count=0)


def attach_ratings(destinations) -> list:
    """Ajoute `rating_summary` à chaque destination, en une seule requête pour toute la liste."""
    destinations = list(destinations)
    rows = (
        Review.objects.public()
        .filter(order__destination__in=[destination.pk for destination in destinations])
        .order_by()  # sans tri : le regroupement porte sur la seule destination
        .values("order__destination")
        .annotate(count=Count("pk"), average=Avg("rating"))
    )
    summaries = {row["order__destination"]: RatingSummary(_one_decimal(row["average"]), row["count"]) for row in rows}
    for destination in destinations:
        destination.rating_summary = summaries.get(destination.pk, NO_REVIEWS)
    return destinations


def destination_reviews(destination, order: str = NEWEST_FIRST, stars: int | None = None):
    """Avis publics d'une destination, triés (plus récents par défaut) et filtrés par nombre d'étoiles."""
    reviews = Review.objects.public().filter(order__destination=destination).select_related("order__client", "response")
    if stars:
        reviews = reviews.filter(rating=stars)
    return reviews.order_by(*REVIEW_ORDERS.get(order, REVIEW_ORDERS[NEWEST_FIRST]))


def latest_top_reviews(limit: int = 5):
    """Derniers avis publics à 5 étoiles (page d'accueil), du plus récemment publié au plus ancien."""
    return (
        Review.objects.public()
        .filter(rating=MAX_RATING)
        .select_related("order__client", "order__destination")
        .order_by("-published_at", "-pk")[:limit]
    )


def _one_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

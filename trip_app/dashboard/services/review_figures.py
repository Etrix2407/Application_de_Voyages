"""Avis pour le tableau de pilotage : note moyenne de l'agence, avis publiés, destinations les mieux et moins bien notées.

- Seuls les avis publiés comptent, y compris ceux d'une destination qui n'est plus proposée
  (l'administrateur voit tout ; la page publique, elle, les masque).
- Les avis comptent selon leur jour de publication à Bruxelles : la base de date de la période
  (commande ou départ) ne concerne que les commandes et ne s'applique pas aux avis.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Count, Q

from dashboard.services.comparison import Comparison, compare
from dashboard.services.periods import Period
from reviews.models import MAX_RATING, Review, ReviewStatus
from reviews.services.ratings import one_decimal

# Une destination n'est classée qu'à partir de ce nombre d'avis publiés.
MIN_REVIEWS_TO_RANK = 5
RANKING_SIZE = 3


@dataclass(frozen=True)
class RatedDestination:
    name: str
    country_name: str
    average: Decimal
    review_count: int


@dataclass(frozen=True)
class ReviewFigures:
    # Aucun avis publié : None.
    average: Decimal | None
    published_count: int
    comparison: Comparison
    best_rated: list[RatedDestination]
    worst_rated: list[RatedDestination]
    min_reviews_to_rank: int = MIN_REVIEWS_TO_RANK

    @property
    def average_text(self) -> str:
        """« 4,3 / 5 », ou « Pas encore d'avis »."""
        if self.average is None:
            return "Pas encore d'avis"
        return f"{self.average} / {MAX_RATING}".replace(".", ",")


def review_figures(period: Period) -> ReviewFigures:
    published = Review.objects.filter(status=ReviewStatus.PUBLISHED)
    previous = period.previous()
    # __date : jour de publication dans le fuseau du site (Bruxelles).
    figures = published.aggregate(
        average=Avg("rating"),
        current_count=Count("pk", filter=Q(published_at__date__range=(period.start, period.end))),
        previous_count=Count("pk", filter=Q(published_at__date__range=(previous.start, previous.end))),
    )
    best_rated, worst_rated = _rankings(published)
    return ReviewFigures(
        average=one_decimal(figures["average"]) if figures["average"] is not None else None,
        published_count=figures["current_count"],
        comparison=compare(figures["current_count"], figures["previous_count"]),
        best_rated=best_rated,
        worst_rated=worst_rated,
    )


def _rankings(published) -> tuple[list[RatedDestination], list[RatedDestination]]:
    """Les 3 destinations les mieux notées et les 3 moins bien notées (la plus basse d'abord).

    Calculé sur tous les avis publiés, pas seulement ceux de la période : sur un mois,
    presque aucune destination n'atteindrait le seuil de 5 avis.
    Avec moins de 6 destinations classées, les moins bien notées ne reprennent pas
    celles déjà parmi les mieux notées : la seconde liste est plus courte, voire vide.
    """
    rows = (
        published.order_by()
        .values("order__destination", "order__destination__name", "order__destination__country__name")
        .annotate(review_count=Count("pk"), average=Avg("rating"))
        .filter(review_count__gte=MIN_REVIEWS_TO_RANK)
        .order_by("-average", "order__destination__name", "order__destination")
    )
    ranked = [
        RatedDestination(
            name=row["order__destination__name"],
            country_name=row["order__destination__country__name"],
            average=one_decimal(row["average"]),
            review_count=row["review_count"],
        )
        for row in rows
    ]
    best_rated = ranked[:RANKING_SIZE]
    worst_rated = ranked[len(best_rated):][-RANKING_SIZE:][::-1]
    return best_rated, worst_rated


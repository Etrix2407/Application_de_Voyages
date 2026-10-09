"""Liste « Tous les avis » du personnel : filtres, du plus récent au plus ancien."""

from reviews.models import NEGATIVE_RATING, Review


def filter_reviews(criteria: dict):
    """Avis correspondant aux critères (formulaire validé), du plus récent au plus ancien."""
    reviews = Review.objects.select_related("order__client")
    if criteria.get("status"):
        reviews = reviews.filter(status=criteria["status"])
    if criteria.get("country"):
        reviews = reviews.filter(order__destination__country=criteria["country"])
    if criteria.get("destination"):
        reviews = reviews.filter(order__destination=criteria["destination"])
    if criteria.get("rating"):
        reviews = reviews.filter(rating=criteria["rating"])
    if criteria.get("negative_only"):
        reviews = reviews.filter(rating__lte=NEGATIVE_RATING)
    # Deux périodes possibles : date de l'avis, ou date du séjour (départ).
    if criteria.get("written_from"):
        reviews = reviews.filter(created_at__date__gte=criteria["written_from"])
    if criteria.get("written_to"):
        reviews = reviews.filter(created_at__date__lte=criteria["written_to"])
    if criteria.get("stay_from"):
        reviews = reviews.filter(order__departure_date__gte=criteria["stay_from"])
    if criteria.get("stay_to"):
        reviews = reviews.filter(order__departure_date__lte=criteria["stay_to"])
    # Le numéro départage les avis créés au même instant : l'ordre ne change pas d'une page à l'autre.
    return reviews.order_by("-created_at", "-pk")

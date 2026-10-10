"""Effets sur les avis des événements des demandes de voyage."""

from reviews.models import RefusalReason, Review, ReviewStatus
from reviews.services.notifications import notify_refused


def hide_review_of_cancelled_order(order) -> None:
    """Voyage annulé après coup : l'avis n'est plus vérifié, il est retiré du public.

    Il passe « Refusé » avec le motif « Voyage annulé » ; le client voit pourquoi et en est
    prévenu par e-mail (sans rappel de correction : l'avis d'un voyage annulé n'est plus modifiable).
    """
    reviews = Review.objects.filter(order=order).exclude(
        status=ReviewStatus.REFUSED, refusal_reason=RefusalReason.TRIP_CANCELLED
    )
    review = reviews.select_related("order__client").first()
    if review is None:
        return
    fields = {"status": ReviewStatus.REFUSED, "refusal_reason": RefusalReason.TRIP_CANCELLED, "refusal_details": ""}
    if not reviews.update(**fields):
        return
    for name, value in fields.items():
        setattr(review, name, value)
    notify_refused(review)

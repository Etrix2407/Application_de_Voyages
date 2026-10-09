"""Effets sur les avis des événements des demandes de voyage."""

from reviews.models import RefusalReason, Review, ReviewStatus


def hide_review_of_cancelled_order(order) -> None:
    """Voyage annulé après coup : l'avis n'est plus vérifié, il est retiré du public.

    Il passe « Refusé » avec le motif « Voyage annulé » ; le client voit pourquoi.
    """
    Review.objects.filter(order=order).exclude(
        status=ReviewStatus.REFUSED, refusal_reason=RefusalReason.TRIP_CANCELLED
    ).update(status=ReviewStatus.REFUSED, refusal_reason=RefusalReason.TRIP_CANCELLED, refusal_details="")

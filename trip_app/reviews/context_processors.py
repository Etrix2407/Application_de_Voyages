"""Compteur « Avis à modérer (N) » affiché dans le menu du personnel."""

from reviews.models import Review, ReviewStatus


def pending_reviews(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff_member:
        return {}
    return {"pending_reviews_count": Review.objects.filter(status=ReviewStatus.PENDING).count()}

"""Compteur « Avis à modérer (N) » affiché dans le menu du personnel."""

from reviews.services.moderation import pending_reviews


def moderation_counter(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff_member:
        return {}
    return {"pending_reviews_count": pending_reviews().count()}

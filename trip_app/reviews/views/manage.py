"""Avis côté personnel : file de modération, détail, publication, refus ou masquage."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from reviews.forms import RefusalForm
from reviews.models import Review, ReviewStatus
from reviews.services.moderation import ModerationNotAllowed, hide, pending_reviews, publish, refuse


def _get_review(pk) -> Review:
    return get_object_or_404(Review.objects.select_related("order__client"), pk=pk)


@staff_required
def pending_list(request):
    return render(request, "reviews/manage/pending.html", {"reviews": pending_reviews()})


@staff_required
def review_detail(request, pk):
    review = _get_review(pk)
    context = {
        "review": review,
        "can_publish": review.status == ReviewStatus.PENDING,
        "can_refuse": review.status in (ReviewStatus.PENDING, ReviewStatus.PUBLISHED),
    }
    return render(request, "reviews/manage/detail.html", context)


@staff_required
@require_POST
def publish_review(request, pk):
    review = _get_review(pk)
    try:
        publish(review)
    except ModerationNotAllowed as error:
        messages.error(request, str(error))
        return redirect("manage_review_detail", pk=review.pk)
    messages.success(request, f"L'avis « {review.title} » est publié.")
    return redirect("manage_pending_reviews")


@staff_required
def refuse_review(request, pk):
    """Refuse un avis en attente, ou masque un avis publié : motif obligatoire."""
    review = _get_review(pk)
    is_hiding = review.status == ReviewStatus.PUBLISHED
    form = RefusalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        action = hide if is_hiding else refuse
        try:
            action(review, form.cleaned_data["reason"], form.cleaned_data["details"])
        except ModerationNotAllowed as error:
            messages.error(request, str(error))
            return redirect("manage_review_detail", pk=review.pk)
        messages.success(request, f"L'avis « {review.title} » est {'masqué' if is_hiding else 'refusé'}.")
        return redirect("manage_pending_reviews")
    return render(request, "reviews/manage/refuse.html", {"review": review, "form": form, "is_hiding": is_hiding})

"""Avis côté personnel : file de modération, détail, publication, refus ou masquage."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from reviews.forms import RefusalForm, ResponseForm
from reviews.models import Review, ReviewStatus
from reviews.services.moderation import ModerationNotAllowed, hide, pending_reviews, publish, refuse
from reviews.services.responses import ResponseNotAllowed, can_write_response, existing_response, save_response


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
        "response": existing_response(review),
        "can_respond": can_write_response(review, request.user),
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


@staff_required
def respond_review(request, pk):
    """Écrit ou modifie la réponse de l'agence (avis publié, auteur de la réponse)."""
    review = _get_review(pk)
    if not can_write_response(review, request.user):
        messages.error(request, "Vous ne pouvez pas répondre à cet avis : il doit être publié, et seul l'auteur "
                                "d'une réponse peut la modifier.")
        return redirect("manage_review_detail", pk=review.pk)
    response = existing_response(review)
    form = ResponseForm(request.POST or None, initial={"text": response.text if response else ""})
    if request.method == "POST" and form.is_valid():
        try:
            save_response(review, request.user, form.cleaned_data["text"])
        except ResponseNotAllowed:
            messages.error(request, "Vous ne pouvez pas répondre à cet avis.")
        else:
            messages.success(request, "La réponse de l'agence est publiée sous l'avis.")
        return redirect("manage_review_detail", pk=review.pk)
    return render(request, "reviews/manage/respond.html", {"review": review, "form": form, "response": response})

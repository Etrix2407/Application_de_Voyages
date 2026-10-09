"""Avis côté client : donner, modifier, supprimer, suivre ses avis."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import client_required
from orders.models import Order
from reviews.forms import ReviewForm
from reviews.models import Review, ReviewStatus
from reviews.services.eligibility import can_review, reviewable_orders
from reviews.services.writing import (
    ReviewLocked,
    ReviewNotAllowed,
    client_can_delete,
    client_can_edit,
    delete_review,
    update_review,
    write_review,
)

LOCKED_MESSAGE = "Cet avis ne peut plus être modifié."
NOT_YET_MESSAGE = "Vous pourrez donner votre avis après votre retour, pour un voyage confirmé par l'agence."
EDITED_MESSAGE = "Votre avis est modifié. Il sera de nouveau publié après validation par l'agence."


def _own_review(request, pk) -> Review:
    """Un client n'accède qu'à ses propres avis (404 sinon)."""
    return get_object_or_404(Review.objects.select_related("order"), pk=pk, order__client=request.user)


@client_required
def my_reviews(request):
    reviews = Review.objects.filter(order__client=request.user).select_related("order", "response")
    context = {
        "to_review": reviewable_orders(request.user).order_by("-return_date", "-pk"),
        "reviews": [(review, client_can_edit(review)) for review in reviews],
    }
    return render(request, "reviews/my_reviews.html", context)


@client_required
def create_review(request, order_pk):
    order = get_object_or_404(Order, pk=order_pk, client=request.user)
    if not can_review(request.user, order):
        messages.error(request, NOT_YET_MESSAGE)
        return redirect("my_order_detail", pk=order.pk)
    form = ReviewForm(request.POST or None, instance=Review(order=order))
    if request.method == "POST" and form.is_valid():
        try:
            write_review(request.user, form.instance)
        except ReviewNotAllowed:
            messages.error(request, "Ce voyage ne peut pas recevoir d'avis.")
        else:
            messages.success(request, "Merci ! Votre avis sera publié après sa validation par l'agence.")
        return redirect("my_reviews")
    return render(request, "reviews/write.html", {"form": form, "order": order})


@client_required
def edit_review(request, pk):
    review = _own_review(request, pk)
    if not client_can_edit(review):
        messages.error(request, LOCKED_MESSAGE)
        return redirect("my_reviews")
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        try:
            update_review(form.instance)
        except ReviewLocked:
            messages.error(request, LOCKED_MESSAGE)
        else:
            messages.success(request, EDITED_MESSAGE)
        return redirect("my_reviews")
    is_published = review.status == ReviewStatus.PUBLISHED
    context = {"form": form, "order": review.order, "review": review, "is_published": is_published}
    return render(request, "reviews/write.html", context)


@client_required
@require_http_methods(["GET", "POST"])
def remove_review(request, pk):
    review = _own_review(request, pk)
    if not client_can_delete(review):
        messages.error(request, LOCKED_MESSAGE)
        return redirect("my_reviews")
    if request.method == "POST":
        delete_review(review)
        messages.success(request, "Votre avis a été supprimé.")
        return redirect("my_reviews")
    return render(request, "reviews/delete.html", {"review": review})

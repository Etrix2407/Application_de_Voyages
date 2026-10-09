"""Pages générales du site."""

from django.shortcuts import render

from reviews.services.ratings import latest_top_reviews


def home(request):
    return render(request, "home.html", {"top_reviews": latest_top_reviews()})

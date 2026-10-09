"""Consultation du catalogue, ouverte à tous : seuls les éléments visibles (actifs) sont montrés."""

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from catalog.models import Activity, Continent, Country, Destination
from catalog.services.favorites import is_favorite
from reviews.forms import PublicReviewFilterForm
from reviews.services.ratings import attach_ratings, destination_reviews

REVIEWS_PER_PAGE = 10


def country_list(request):
    """Liste publique des pays, groupés par continent."""
    visible_countries = Country.objects.visible()
    continents = [
        (continent.label, [country for country in visible_countries if country.continent == continent])
        for continent in Continent
    ]
    context = {"continents": [(name, countries) for name, countries in continents if countries]}
    return render(request, "catalog/country_list.html", context)


def country_detail(request, pk):
    country = get_object_or_404(Country.objects.visible(), pk=pk)
    context = {
        "country": country,
        "time_offsets": country.time_offsets(),
        "destinations": attach_ratings(Destination.objects.visible().filter(country=country)),
        "activities": Activity.objects.visible().filter(country=country),
    }
    return render(request, "catalog/country.html", context)


def destination_detail(request, pk):
    destination = get_object_or_404(
        Destination.objects.visible().select_related("country"), pk=pk
    )
    attach_ratings([destination])
    filters = PublicReviewFilterForm(request.GET or None)
    criteria = filters.cleaned_data if filters.is_valid() else {}
    reviews = destination_reviews(destination, criteria.get("sort") or "", criteria.get("stars"))
    context = {
        "destination": destination,
        "activities": Activity.objects.visible().filter(destination=destination),
        "is_favorite": is_favorite(request.user, destination),
        "review_filters": filters,
        "reviews_page": Paginator(reviews, REVIEWS_PER_PAGE).get_page(request.GET.get("page")),
    }
    return render(request, "catalog/destination.html", context)


def destination_list(request):
    """Toutes les destinations proposées, avec leur note moyenne."""
    destinations = Destination.objects.visible().select_related("country").order_by("country__name", "name", "pk")
    return render(request, "catalog/destination_list.html", {"destinations": attach_ratings(destinations)})


def activity_detail(request, pk):
    activity = get_object_or_404(
        Activity.objects.visible().select_related("country", "destination"), pk=pk
    )
    context = {"activity": activity, "is_favorite": is_favorite(request.user, activity)}
    return render(request, "catalog/activity.html", context)

"""Consultation du catalogue : seuls les éléments visibles (actifs) sont montrés."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from catalog.models import Activity, Continent, Country, Destination
from catalog.services.favorites import is_favorite


def country_list(request):
    """Liste publique des pays, groupés par continent."""
    visible_countries = Country.objects.visible()
    continents = [
        (continent.label, [country for country in visible_countries if country.continent == continent])
        for continent in Continent
    ]
    context = {"continents": [(name, countries) for name, countries in continents if countries]}
    return render(request, "catalog/country_list.html", context)


@login_required
def country_detail(request, pk):
    country = get_object_or_404(Country.objects.visible(), pk=pk)
    context = {
        "country": country,
        "destinations": Destination.objects.visible().filter(country=country),
        "activities": Activity.objects.visible().filter(country=country),
    }
    return render(request, "catalog/country.html", context)


@login_required
def destination_detail(request, pk):
    destination = get_object_or_404(
        Destination.objects.visible().select_related("country"), pk=pk
    )
    context = {
        "destination": destination,
        "activities": Activity.objects.visible().filter(destination=destination),
        "is_favorite": is_favorite(request.user, destination),
    }
    return render(request, "catalog/destination.html", context)


@login_required
def activity_detail(request, pk):
    activity = get_object_or_404(
        Activity.objects.visible().select_related("country", "destination"), pk=pk
    )
    context = {"activity": activity, "is_favorite": is_favorite(request.user, activity)}
    return render(request, "catalog/activity.html", context)

"""Gestion du catalogue par le personnel (règle 6), organisée par pays."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import staff_required
from catalog.forms import ActivityForm, CountryForm, DestinationForm
from catalog.models import Activity, Country, Destination


def _country_page_url(item: Country | Destination | Activity) -> str:
    """Après chaque action, on revient à la fiche du pays concerné."""
    country_pk = item.pk if isinstance(item, Country) else item.country_id
    return reverse("manage_country", args=[country_pk])


def _render_form(request, form, title: str, back_url: str):
    """Affiche le formulaire ; s'il est valide, enregistre et revient à la fiche du pays."""
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, f"« {item} » a été enregistré.")
        return redirect(_country_page_url(item))
    context = {"form": form, "title": title, "back_url": back_url}
    return render(request, "catalog/manage/form.html", context)


def _confirm_delete(request, item, back_url: str, consequence: str = ""):
    """Page de confirmation, puis suppression définitive en POST."""
    if request.method == "POST":
        item.delete()
        messages.success(request, f"« {item} » a été supprimé.")
        return redirect(back_url)
    context = {"item": item, "back_url": back_url, "consequence": consequence}
    return render(request, "catalog/manage/delete.html", context)


# Pays


@staff_required
def country_list(request):
    countries = Country.objects.annotate(
        destination_count=Count("destinations", distinct=True),
        activity_count=Count("activities", distinct=True),
    )
    return render(request, "catalog/manage/country_list.html", {"countries": countries})


@staff_required
def country_page(request, pk):
    country = get_object_or_404(Country, pk=pk)
    context = {
        "country": country,
        "destinations": country.destinations.all(),
        "activities": country.activities.select_related("destination"),
    }
    return render(request, "catalog/manage/country.html", context)


@staff_required
def create_country(request):
    form = CountryForm(request.POST or None)
    return _render_form(request, form, "Ajouter un pays", reverse("manage_country_list"))


@staff_required
def edit_country(request, pk):
    country = get_object_or_404(Country, pk=pk)
    form = CountryForm(request.POST or None, instance=country)
    return _render_form(request, form, f"Modifier le pays « {country} »", _country_page_url(country))


@staff_required
def delete_country(request, pk):
    country = get_object_or_404(Country, pk=pk)
    if not country.can_be_deleted():
        messages.error(
            request,
            f"« {country} » contient des destinations ou des activités : il ne peut pas être "
            "supprimé. Vous pouvez le désactiver pour le masquer aux clients.",
        )
        return redirect(_country_page_url(country))
    return _confirm_delete(request, country, reverse("manage_country_list"))


# Destinations


@staff_required
def create_destination(request, country_pk):
    country = get_object_or_404(Country, pk=country_pk)
    form = DestinationForm(request.POST or None, request.FILES or None, country=country)
    return _render_form(request, form, f"Ajouter une destination — {country}", _country_page_url(country))


@staff_required
def edit_destination(request, pk):
    destination = get_object_or_404(Destination.objects.select_related("country"), pk=pk)
    form = DestinationForm(
        request.POST or None, request.FILES or None, instance=destination, country=destination.country
    )
    title = f"Modifier la destination « {destination} » — {destination.country}"
    return _render_form(request, form, title, _country_page_url(destination))


@staff_required
def delete_destination(request, pk):
    destination = get_object_or_404(Destination, pk=pk)
    consequence = (
        "Les activités liées à cette destination restent dans le pays, sans destination précise."
        if destination.activities.exists()
        else ""
    )
    return _confirm_delete(request, destination, _country_page_url(destination), consequence)


# Activités


@staff_required
def create_activity(request, country_pk):
    country = get_object_or_404(Country, pk=country_pk)
    form = ActivityForm(request.POST or None, country=country)
    return _render_form(request, form, f"Ajouter une activité — {country}", _country_page_url(country))


@staff_required
def edit_activity(request, pk):
    activity = get_object_or_404(Activity.objects.select_related("country"), pk=pk)
    form = ActivityForm(request.POST or None, instance=activity, country=activity.country)
    title = f"Modifier l'activité « {activity} » — {activity.country}"
    return _render_form(request, form, title, _country_page_url(activity))


@staff_required
def delete_activity(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    return _confirm_delete(request, activity, _country_page_url(activity))

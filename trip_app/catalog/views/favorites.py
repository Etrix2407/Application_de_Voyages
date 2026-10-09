"""Favoris des clients : chacun ne voit et ne gère que les siens (règle 7)."""

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import client_required
from catalog.models import Activity, Destination, FavoriteActivity, FavoriteDestination
from reviews.services.ratings import attach_ratings

# Type d'élément (dans l'URL) -> (modèle, modèle de favori, nom du champ, page de détail).
ITEM_TYPES = {
    "destination": (Destination, FavoriteDestination, "destination", "destination_detail"),
    "activite": (Activity, FavoriteActivity, "activity", "activity_detail"),
}


def _get_item_type(name: str):
    if name not in ITEM_TYPES:
        raise Http404
    return ITEM_TYPES[name]


def _redirect_back(request, default: str) -> HttpResponseRedirect:
    """Revient à la page d'origine si c'est un chemin interne au site, sinon à `default`.

    Le texte reçu n'est jamais interprété comme un nom de vue (évite une erreur 500).
    """
    next_url = request.POST.get("next", "")
    is_internal = next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    )
    return HttpResponseRedirect(next_url if is_internal else default)


@client_required
@require_POST
def add_favorite(request, item_type, pk):
    model, favorite_model, field_name, detail_url_name = _get_item_type(item_type)
    # On ne peut ajouter qu'un élément visible du catalogue.
    item = get_object_or_404(model.objects.visible(), pk=pk)
    favorite_model.objects.get_or_create(client=request.user, **{field_name: item})
    messages.success(request, f"« {item} » a été ajouté à vos favoris.")
    return _redirect_back(request, reverse(detail_url_name, args=[pk]))


@client_required
@require_POST
def remove_favorite(request, item_type, pk):
    _, favorite_model, field_name, _ = _get_item_type(item_type)
    deleted, _ = favorite_model.objects.filter(client=request.user, **{f"{field_name}_id": pk}).delete()
    if deleted:
        messages.success(request, "L'élément a été retiré de vos favoris.")
    return _redirect_back(request, reverse("favorite_list"))


@client_required
def favorite_list(request):
    visible_destinations = set(Destination.objects.visible().values_list("pk", flat=True))
    visible_activities = set(Activity.objects.visible().values_list("pk", flat=True))
    favorites = FavoriteDestination.objects.filter(client=request.user).select_related("destination__country")
    destinations = attach_ratings(favorite.destination for favorite in favorites)
    context = {
        "favorite_destinations": [
            (destination, destination.pk in visible_destinations) for destination in destinations
        ],
        "favorite_activities": [
            (favorite.activity, favorite.activity_id in visible_activities)
            for favorite in FavoriteActivity.objects.filter(client=request.user).select_related(
                "activity__country"
            )
        ],
    }
    return render(request, "catalog/favorites.html", context)

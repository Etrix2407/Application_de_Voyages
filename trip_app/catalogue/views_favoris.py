"""Favoris des clients : chacun ne voit et ne gère que les siens (règle 7)."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from comptes.decorators import client_requis

from .models import Activite, Destination, FavoriActivite, FavoriDestination

# Type d'élément (dans l'URL) -> (modèle, modèle de favori, nom du champ, page de détail).
TYPES = {
    "destination": (Destination, FavoriDestination, "destination", "detail_destination"),
    "activite": (Activite, FavoriActivite, "activite", "detail_activite"),
}


def _type(nom: str):
    if nom not in TYPES:
        raise Http404
    return TYPES[nom]


def _page_suivante(request, defaut: str) -> str:
    suivant = request.POST.get("suivant", "")
    if url_has_allowed_host_and_scheme(suivant, allowed_hosts={request.get_host()}):
        return suivant
    return defaut


@client_requis
@require_POST
def ajouter(request, type_element, pk):
    modele, modele_favori, champ, page_detail = _type(type_element)
    # On ne peut ajouter qu'un élément visible du catalogue.
    element = get_object_or_404(modele.objects.visibles(), pk=pk)
    modele_favori.objects.get_or_create(client=request.user, **{champ: element})
    messages.success(request, f"« {element} » a été ajouté à vos favoris.")
    return redirect(_page_suivante(request, reverse(page_detail, args=[pk])))


@client_requis
@require_POST
def retirer(request, type_element, pk):
    _, modele_favori, champ, _ = _type(type_element)
    supprimes, _ = modele_favori.objects.filter(client=request.user, **{f"{champ}_id": pk}).delete()
    if supprimes:
        messages.success(request, "L'élément a été retiré de vos favoris.")
    return redirect(_page_suivante(request, reverse("mes_favoris")))


@client_requis
def mes_favoris(request):
    destinations_visibles = set(Destination.objects.visibles().values_list("pk", flat=True))
    activites_visibles = set(Activite.objects.visibles().values_list("pk", flat=True))
    contexte = {
        "favoris_destinations": [
            (favori.destination, favori.destination_id in destinations_visibles)
            for favori in FavoriDestination.objects.filter(client=request.user).select_related(
                "destination__pays"
            )
        ],
        "favoris_activites": [
            (favori.activite, favori.activite_id in activites_visibles)
            for favori in FavoriActivite.objects.filter(client=request.user).select_related(
                "activite__pays"
            )
        ],
    }
    return render(request, "catalogue/mes_favoris.html", contexte)


def est_favori(utilisateur, element: Destination | Activite) -> bool:
    """Pour afficher le bon bouton sur les pages de détail (clients uniquement)."""
    if not utilisateur.est_client:
        return False
    if isinstance(element, Destination):
        return FavoriDestination.objects.filter(client=utilisateur, destination=element).exists()
    return FavoriActivite.objects.filter(client=utilisateur, activite=element).exists()

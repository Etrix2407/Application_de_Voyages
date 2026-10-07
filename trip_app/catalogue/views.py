"""Consultation du catalogue : seuls les éléments visibles (actifs) sont montrés."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Activite, Continent, Destination, Pays


def liste_pays(request):
    """Liste publique des pays, groupés par continent."""
    pays_visibles = Pays.objects.visibles()
    continents = [
        (continent.label, [pays for pays in pays_visibles if pays.continent == continent])
        for continent in Continent
    ]
    contexte = {"continents": [(nom, liste) for nom, liste in continents if liste]}
    return render(request, "catalogue/liste_pays.html", contexte)


@login_required
def detail_pays(request, pk):
    pays = get_object_or_404(Pays.objects.visibles(), pk=pk)
    contexte = {
        "pays": pays,
        "destinations": Destination.objects.visibles().filter(pays=pays),
        "activites": Activite.objects.visibles().filter(pays=pays),
    }
    return render(request, "catalogue/pays.html", contexte)


@login_required
def detail_destination(request, pk):
    destination = get_object_or_404(
        Destination.objects.visibles().select_related("pays"), pk=pk
    )
    contexte = {
        "destination": destination,
        "activites": Activite.objects.visibles().filter(destination=destination),
    }
    return render(request, "catalogue/destination.html", contexte)


@login_required
def detail_activite(request, pk):
    activite = get_object_or_404(
        Activite.objects.visibles().select_related("pays", "destination"), pk=pk
    )
    return render(request, "catalogue/activite.html", {"activite": activite})

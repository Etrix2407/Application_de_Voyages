"""Gestion du catalogue par le personnel (règle 6), organisée par pays."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from comptes.decorators import personnel_requis

from .forms import ActiviteForm, DestinationForm, PaysForm
from .models import Activite, Destination, Pays


def _url_fiche(objet: Pays | Destination | Activite) -> str:
    """Après chaque action, on revient à la fiche du pays concerné."""
    pays_pk = objet.pk if isinstance(objet, Pays) else objet.pays_id
    return reverse("gestion_pays", args=[pays_pk])


def _formulaire(request, form, titre: str, retour_url: str):
    """Affiche le formulaire ; s'il est valide, enregistre et revient à la fiche du pays."""
    if request.method == "POST" and form.is_valid():
        objet = form.save()
        messages.success(request, f"« {objet} » a été enregistré.")
        return redirect(_url_fiche(objet))
    contexte = {"form": form, "titre": titre, "retour_url": retour_url}
    return render(request, "catalogue/gestion/formulaire.html", contexte)


def _suppression(request, objet, retour_url: str, consequence: str = ""):
    """Page de confirmation, puis suppression définitive en POST."""
    if request.method == "POST":
        objet.delete()
        messages.success(request, f"« {objet} » a été supprimé.")
        return redirect(retour_url)
    contexte = {"objet": objet, "retour_url": retour_url, "consequence": consequence}
    return render(request, "catalogue/gestion/supprimer.html", contexte)


# Pays


@personnel_requis
def liste_pays(request):
    liste = Pays.objects.annotate(
        nb_destinations=Count("destinations", distinct=True),
        nb_activites=Count("activites", distinct=True),
    )
    return render(request, "catalogue/gestion/liste_pays.html", {"liste_pays": liste})


@personnel_requis
def fiche_pays(request, pk):
    pays = get_object_or_404(Pays, pk=pk)
    contexte = {
        "pays": pays,
        "destinations": pays.destinations.all(),
        "activites": pays.activites.select_related("destination"),
    }
    return render(request, "catalogue/gestion/pays.html", contexte)


@personnel_requis
def creer_pays(request):
    form = PaysForm(request.POST or None)
    return _formulaire(request, form, "Ajouter un pays", reverse("gestion_liste_pays"))


@personnel_requis
def modifier_pays(request, pk):
    pays = get_object_or_404(Pays, pk=pk)
    form = PaysForm(request.POST or None, instance=pays)
    return _formulaire(request, form, f"Modifier le pays « {pays} »", _url_fiche(pays))


@personnel_requis
def supprimer_pays(request, pk):
    pays = get_object_or_404(Pays, pk=pk)
    if not pays.peut_etre_supprime():
        messages.error(
            request,
            f"« {pays} » contient des destinations ou des activités : il ne peut pas être "
            "supprimé. Vous pouvez le désactiver pour le masquer aux clients.",
        )
        return redirect(_url_fiche(pays))
    return _suppression(request, pays, reverse("gestion_liste_pays"))


# Destinations


@personnel_requis
def creer_destination(request, pays_pk):
    pays = get_object_or_404(Pays, pk=pays_pk)
    form = DestinationForm(request.POST or None, pays=pays)
    return _formulaire(request, form, f"Ajouter une destination — {pays}", _url_fiche(pays))


@personnel_requis
def modifier_destination(request, pk):
    destination = get_object_or_404(Destination.objects.select_related("pays"), pk=pk)
    form = DestinationForm(request.POST or None, instance=destination, pays=destination.pays)
    titre = f"Modifier la destination « {destination} » — {destination.pays}"
    return _formulaire(request, form, titre, _url_fiche(destination))


@personnel_requis
def supprimer_destination(request, pk):
    destination = get_object_or_404(Destination, pk=pk)
    consequence = (
        "Les activités liées à cette destination restent dans le pays, sans destination précise."
        if destination.activites.exists()
        else ""
    )
    return _suppression(request, destination, _url_fiche(destination), consequence)


# Activités


@personnel_requis
def creer_activite(request, pays_pk):
    pays = get_object_or_404(Pays, pk=pays_pk)
    form = ActiviteForm(request.POST or None, pays=pays)
    return _formulaire(request, form, f"Ajouter une activité — {pays}", _url_fiche(pays))


@personnel_requis
def modifier_activite(request, pk):
    activite = get_object_or_404(Activite.objects.select_related("pays"), pk=pk)
    form = ActiviteForm(request.POST or None, instance=activite, pays=activite.pays)
    titre = f"Modifier l'activité « {activite} » — {activite.pays}"
    return _formulaire(request, form, titre, _url_fiche(activite))


@personnel_requis
def supprimer_activite(request, pk):
    activite = get_object_or_404(Activite, pk=pk)
    return _suppression(request, activite, _url_fiche(activite))

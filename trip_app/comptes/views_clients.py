"""Consultation et correction des comptes clients par le personnel."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogue.recherche import normaliser

from .decorators import personnel_requis
from .emails import envoyer_lien_mot_de_passe
from .forms import CorrectionClientForm
from .models import Role, Utilisateur

CLIENTS_PAR_PAGE = 25


def _client(pk: int) -> Utilisateur:
    """Seuls les comptes clients sont accessibles ici, jamais ceux du personnel."""
    return get_object_or_404(Utilisateur, pk=pk, role=Role.CLIENT)


@personnel_requis
def liste_clients(request):
    recherche = request.GET.get("q", "").strip()
    clients = Utilisateur.objects.filter(role=Role.CLIENT).order_by("nom", "prenom")
    mots = normaliser(recherche).split()
    if mots:
        # Filtre en Python : SQLite ne sait pas ignorer les accents (~1 000 clients).
        clients = [
            client
            for client in clients
            if all(mot in normaliser(f"{client.nom} {client.prenom} {client.email}") for mot in mots)
        ]
    page = Paginator(clients, CLIENTS_PAR_PAGE).get_page(request.GET.get("page"))
    return render(request, "comptes/clients/liste.html", {"page": page, "recherche": recherche})


@personnel_requis
def modifier_client(request, pk):
    client = _client(pk)
    form = CorrectionClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Les informations de {client.get_full_name()} ont été corrigées.")
        return redirect("liste_clients")
    return render(request, "comptes/clients/modifier.html", {"form": form, "client": client})


@personnel_requis
@require_POST
def envoyer_lien_client(request, pk):
    client = _client(pk)
    envoyer_lien_mot_de_passe(
        request, client, "Changement de votre mot de passe", "comptes/email_lien_client.txt"
    )
    messages.success(request, f"Un lien pour choisir un nouveau mot de passe a été envoyé à {client.email}.")
    return redirect("modifier_client", pk=client.pk)

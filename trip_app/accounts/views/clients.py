"""Consultation et correction des comptes clients par le personnel."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from accounts.forms import ClientCorrectionForm
from accounts.models import Role, User
from accounts.services.client_search import client_matches, search_words
from accounts.services.emails import send_password_link

CLIENTS_PER_PAGE = 25


def _get_client(pk: int) -> User:
    """Seuls les comptes clients sont accessibles ici, jamais ceux du personnel."""
    return get_object_or_404(User, pk=pk, role=Role.CLIENT)


@staff_required
def client_list(request):
    query = request.GET.get("q", "").strip()
    clients = User.objects.filter(role=Role.CLIENT).order_by("last_name", "first_name", "pk")
    words = search_words(query)
    if words:
        # Filtre en Python (~1 000 clients) : voir client_matches.
        clients = [client for client in clients if client_matches(client, words)]
    page = Paginator(clients, CLIENTS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "accounts/clients/list.html", {"page": page, "query": query})


@staff_required
def edit_client(request, pk):
    client = _get_client(pk)
    form = ClientCorrectionForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Les informations de {client.get_full_name()} ont été corrigées.")
        return redirect("client_list")
    return render(request, "accounts/clients/edit.html", {"form": form, "client": client})


@staff_required
@require_POST
def send_client_link(request, pk):
    client = _get_client(pk)
    sent = send_password_link(
        request, client, "Changement de votre mot de passe", "accounts/emails/client_password.txt"
    )
    if sent:
        messages.success(request, f"Un lien pour choisir un nouveau mot de passe a été envoyé à {client.email}.")
    else:
        messages.error(request, "Le lien n'a pas pu être envoyé (problème de messagerie). Réessayez plus tard.")
    return redirect("edit_client", pk=client.pk)

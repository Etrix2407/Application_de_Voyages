"""Consultation et correction des comptes clients par le personnel."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from config.text import normalize

from .decorators import staff_required
from .emails import send_password_link
from .forms import ClientCorrectionForm
from .models import Role, User

CLIENTS_PER_PAGE = 25


def _get_client(pk: int) -> User:
    """Seuls les comptes clients sont accessibles ici, jamais ceux du personnel."""
    return get_object_or_404(User, pk=pk, role=Role.CLIENT)


@staff_required
def client_list(request):
    query = request.GET.get("q", "").strip()
    clients = User.objects.filter(role=Role.CLIENT).order_by("last_name", "first_name")
    words = normalize(query).split()
    if words:
        # Filtre en Python : SQLite ne sait pas ignorer les accents (~1 000 clients).
        clients = [
            client
            for client in clients
            if all(keyword in normalize(f"{client.last_name} {client.first_name} {client.email}") for keyword in words)
        ]
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
    send_password_link(
        request, client, "Changement de votre mot de passe", "accounts/client_password_email.txt"
    )
    messages.success(request, f"Un lien pour choisir un nouveau mot de passe a été envoyé à {client.email}.")
    return redirect("edit_client", pk=client.pk)

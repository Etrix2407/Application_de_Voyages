"""Consultation et correction des comptes clients par le personnel."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from accounts.forms import ClientCorrectionForm
from accounts.models import EmailKind, Role, User
from accounts.services.address_check import with_address_to_check
from accounts.services.client_search import matching_clients, search_words
from accounts.services.password_links import send_password_link

CLIENTS_PER_PAGE = 25


def _get_client(pk: int) -> User:
    """Seuls les comptes clients sont accessibles ici, jamais ceux du personnel."""
    return get_object_or_404(User, pk=pk, role=Role.CLIENT)


def _list_query(request) -> str:
    """Recherche et page de la liste (?q=…&page=…), gardées pendant la correction d'un client.

    La liste est toujours reconstruite à partir de ces deux valeurs : aucune adresse de retour
    venant de la requête n'est suivie telle quelle.
    """
    return urlencode({key: request.GET[key] for key in ("q", "page") if request.GET.get(key)})


def _with_query(url: str, query: str) -> str:
    return f"{url}?{query}" if query else url


@staff_required
def client_list(request):
    query = request.GET.get("q", "").strip()
    clients = with_address_to_check(matching_clients(search_words(query))).order_by("last_name", "first_name", "pk")
    page = Paginator(clients, CLIENTS_PER_PAGE).get_page(request.GET.get("page"))
    context = {"page": page, "query": query, "list_query": _list_query(request)}
    return render(request, "accounts/clients/list.html", context)


@staff_required
def edit_client(request, pk):
    client = _get_client(pk)
    list_query = _list_query(request)
    list_url = _with_query(reverse("client_list"), list_query)
    form = ClientCorrectionForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Les informations de {client.get_full_name()} ont été corrigées.")
        return redirect(list_url)
    context = {"form": form, "client": client, "list_url": list_url, "list_query": list_query}
    return render(request, "accounts/clients/edit.html", context)


@staff_required
@require_POST
def send_client_link(request, pk):
    client = _get_client(pk)
    sent = send_password_link(request, client, EmailKind.CLIENT_PASSWORD_LINK)
    if sent:
        messages.success(request, f"Un lien pour choisir un nouveau mot de passe a été envoyé à {client.email}.")
    else:
        messages.error(request, "Le lien n'a pas pu être envoyé (problème de messagerie). Réessayez plus tard.")
    return redirect(_with_query(reverse("edit_client", args=[client.pk]), _list_query(request)))

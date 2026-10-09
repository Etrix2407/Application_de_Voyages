"""Demandes de voyage côté client : création, liste, détail, annulation."""

import uuid

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import client_required
from catalog.models import Destination
from orders.forms import ClientCancelForm, OrderForm
from orders.models import Order, Status
from orders.services.placing import AlreadySubmitted, estimate_for, find_pending_duplicates, place_order
from orders.services.status import TransitionNotAllowed, cancel_by_client


@client_required
def create_order(request, destination_pk):
    """Formulaire, puis page de vérification (prix estimé, doublon), puis envoi."""
    destination = get_object_or_404(Destination.objects.select_related("country"), pk=destination_pk)
    if not Destination.objects.visible().filter(pk=destination.pk).exists():
        # Ex. destination désactivée pendant que le client remplissait sa demande.
        messages.error(request, "Cette destination n'est plus proposée : aucune demande n'a été envoyée.")
        return redirect("country_list")

    form = OrderForm(request.POST or None, client=request.user, destination=destination)
    if request.method != "POST" or "edit" in request.POST or not form.is_valid():
        return render(request, "orders/create.html", {"form": form, "destination": destination})

    data = form.cleaned_data
    price = estimate_for(destination, data["activities"], data["adults"], data["children"])
    if "confirm" not in request.POST:
        return _review(request, form, destination, price)

    expected = request.POST.get("expected_price")
    token = _parse_token(request.POST.get("submission_token"))
    if expected != str(price) or token is None:
        # Un tarif a changé depuis la page de vérification : le client doit revoir le prix.
        return _review(request, form, destination, price, price_changed=expected is not None)
    try:
        order = place_order(request.user, destination, data, submission_token=token)
    except AlreadySubmitted as duplicate:
        messages.info(request, "Cette demande avait déjà été envoyée.")
        return redirect("my_order_detail", pk=duplicate.order.pk)
    messages.success(request, "Votre demande a bien été enregistrée, un conseiller vous rappellera sous 48 heures.")
    return redirect("my_order_detail", pk=order.pk)


def _review(request, form, destination, price, price_changed=False):
    data = form.cleaned_data
    context = {
        "form": form,
        "destination": destination,
        "activities": data["activities"],
        "estimated_price": price,
        # Valeur exacte (non mise en forme) renvoyée à l'envoi pour détecter un changement de tarif.
        "expected_price": str(price),
        "submission_token": uuid.uuid4(),
        "price_changed": price_changed,
        "duplicates": find_pending_duplicates(request.user, destination, data["departure_date"], data["return_date"]),
    }
    return render(request, "orders/review.html", context)


def _parse_token(value):
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def _own_order(request, pk) -> Order:
    """Règle 7 : un client n'accède qu'à ses propres demandes (404 sinon)."""
    return get_object_or_404(Order.objects.select_related("destination__country"), pk=pk, client=request.user)


@client_required
def my_orders(request):
    orders = Order.objects.filter(client=request.user).select_related("destination__country")
    return render(request, "orders/my_orders.html", {"orders": orders})


@client_required
def my_order_detail(request, pk):
    order = _own_order(request, pk)
    context = {
        "order": order,
        "activities": order.activities.select_related("activity"),
        "history": order.history.all(),
        "can_cancel": order.status == Status.PENDING,
        "is_confirmed": order.status == Status.CONFIRMED,
    }
    return render(request, "orders/my_order_detail.html", context)


@client_required
def cancel_my_order(request, pk):
    order = _own_order(request, pk)
    if order.status != Status.PENDING:
        messages.error(request, "Cette demande ne peut plus être annulée en ligne : appelez l'agence.")
        return redirect("my_order_detail", pk=order.pk)

    form = ClientCancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_by_client(order, form.cleaned_data["reason"])
        except TransitionNotAllowed:
            messages.error(request, "Cette demande ne peut plus être annulée en ligne : appelez l'agence.")
        else:
            messages.success(request, "Votre demande a été annulée.")
        return redirect("my_order_detail", pk=order.pk)
    return render(request, "orders/cancel_my_order.html", {"order": order, "form": form})

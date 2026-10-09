"""Demandes de voyage côté client : création, liste, détail, annulation."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import client_required
from catalog.models import Destination
from orders.forms import ClientCancelForm, OrderForm
from orders.models import Order, Status
from orders.services.placing import estimate_for, find_pending_duplicates, place_order
from orders.services.status import TransitionNotAllowed, cancel_by_client


@client_required
def create_order(request, destination_pk):
    """Formulaire, puis page de vérification (prix estimé, doublon), puis envoi."""
    destination = get_object_or_404(Destination.objects.visible().select_related("country"), pk=destination_pk)
    form = OrderForm(request.POST or None, client=request.user, destination=destination)
    context = {"form": form, "destination": destination}

    if request.method == "POST" and "edit" not in request.POST and form.is_valid():
        if "confirm" in request.POST:
            order = place_order(request.user, destination, form.cleaned_data)
            messages.success(
                request,
                "Votre demande a bien été enregistrée, un conseiller vous rappellera sous 48 heures.",
            )
            return redirect("my_order_detail", pk=order.pk)
        data = form.cleaned_data
        context.update(
            activities=data["activities"],
            estimated_price=estimate_for(destination, data["activities"], data["adults"], data["children"]),
            duplicates=find_pending_duplicates(request.user, destination, data["departure_date"], data["return_date"]),
        )
        return render(request, "orders/review.html", context)
    return render(request, "orders/create.html", context)


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

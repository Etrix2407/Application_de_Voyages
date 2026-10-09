"""Demandes de voyage côté client."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import client_required
from catalog.models import Destination
from orders.forms import OrderForm
from orders.services.placing import estimate_for, find_pending_duplicates, place_order


@client_required
def create_order(request, destination_pk):
    """Formulaire, puis page de vérification (prix estimé, doublon), puis envoi."""
    destination = get_object_or_404(Destination.objects.visible().select_related("country"), pk=destination_pk)
    form = OrderForm(request.POST or None, client=request.user, destination=destination)
    context = {"form": form, "destination": destination}

    if request.method == "POST" and "edit" not in request.POST and form.is_valid():
        if "confirm" in request.POST:
            place_order(request.user, destination, form.cleaned_data)
            messages.success(
                request,
                "Votre demande a bien été enregistrée, un conseiller vous rappellera sous 48 heures.",
            )
            return redirect("destination_detail", pk=destination.pk)
        data = form.cleaned_data
        context.update(
            activities=data["activities"],
            estimated_price=estimate_for(destination, data["activities"], data["adults"], data["children"]),
            duplicates=find_pending_duplicates(request.user, destination, data["departure_date"], data["return_date"]),
        )
        return render(request, "orders/review.html", context)
    return render(request, "orders/create.html", context)

"""Demandes de voyage côté personnel : liste filtrée, détail, confirmation et annulation."""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from orders.forms import StaffCancelForm, StaffOrderFilterForm
from orders.models import Order, OrderStatus
from orders.services.filtering import filter_orders
from orders.services.placing import price_at_current_rates
from orders.services.status import (
    PriceChanged,
    TransitionNotAllowed,
    cancel_by_staff,
    confirm_by_staff,
    departure_passed,
    staff_can_cancel,
    staff_can_confirm,
)

ORDERS_PER_PAGE = 25


@staff_required
def order_list(request):
    form = StaffOrderFilterForm(request.GET or None)
    criteria = form.cleaned_data if form.is_valid() else {}
    page = Paginator(filter_orders(criteria), ORDERS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "orders/manage/list.html", {"form": form, "page": page})


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("client", "destination__country"), pk=pk)
    context = {
        "order": order,
        "activities": order.activities.select_related("activity"),
        "history": order.history.all(),
        "show_staff_names": True,
        "show_internal_reasons": True,
        "can_confirm": staff_can_confirm(order),
        "departure_passed": order.status == OrderStatus.PENDING and departure_passed(order),
        "can_cancel": staff_can_cancel(order),
    }
    if context["can_confirm"]:
        # Prix qui sera enregistré si l'agent confirme maintenant.
        context["price_if_confirmed"] = price_at_current_rates(order)
        # Renvoyé à la confirmation : si le prix change entre-temps, l'agent le revoit avant de confirmer.
        context["expected_price"] = str(context["price_if_confirmed"].price)
        context["destination_on_quote_now"] = order.destination.price_from is None
    return render(request, "orders/manage/detail.html", context)


@staff_required
@require_POST
def confirm_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        confirm_by_staff(order, request.user, expected_price=_posted_price(request))
    except (TransitionNotAllowed, PriceChanged) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"La demande n° {order.pk} est confirmée.")
    return redirect("manage_order_detail", pk=order.pk)


# Prix impossible (un prix n'est jamais négatif) : aucun recalcul ne lui correspond.
UNREADABLE_PRICE = Decimal("-1")


def _posted_price(request) -> Decimal:
    """Prix vu par l'agent (champ caché de la page).

    Absent, illisible ou non fini (« NaN ») : un prix impossible, la confirmation est donc refusée
    comme si le prix avait changé, après les contrôles de l'état de la demande.
    """
    try:
        price = Decimal(request.POST.get("expected_price", ""))
    except InvalidOperation:
        return UNREADABLE_PRICE
    return price if price.is_finite() else UNREADABLE_PRICE


@staff_required
def cancel_order(request, pk):
    order = get_object_or_404(Order.objects.select_related("client", "destination"), pk=pk)
    form = StaffCancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_by_staff(
                order, request.user, form.cleaned_data["internal_reason"], form.cleaned_data["explanation"]
            )
        except TransitionNotAllowed as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"La demande n° {order.pk} est annulée.")
        return redirect("manage_order_detail", pk=order.pk)
    return render(request, "orders/manage/cancel.html", {"order": order, "form": form})

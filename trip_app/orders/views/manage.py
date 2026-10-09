"""Demandes de voyage côté personnel : liste filtrée et détail."""

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from accounts.decorators import staff_required
from orders.forms import StaffOrderFilterForm
from orders.models import Order
from orders.services.filtering import filter_orders

ORDERS_PER_PAGE = 25


@staff_required
def order_list(request):
    form = StaffOrderFilterForm(request.GET or None)
    criteria = form.cleaned_data if form.is_valid() else {}
    page = Paginator(filter_orders(criteria), ORDERS_PER_PAGE).get_page(request.GET.get("page"))
    # Les filtres sont conservés d'une page à l'autre.
    query = request.GET.copy()
    query.pop("page", None)
    context = {"form": form, "page": page, "query": query.urlencode()}
    return render(request, "orders/manage/list.html", context)


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("client", "destination__country"), pk=pk)
    context = {
        "order": order,
        "activities": order.activities.select_related("activity"),
        "history": order.history.all(),
    }
    return render(request, "orders/manage/detail.html", context)

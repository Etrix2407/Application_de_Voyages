"""Tableau de bord opérationnel : réservé au personnel, en temps réel (aucun cache)."""

from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse

from accounts.decorators import staff_required
from dashboard.services.operational import OrderFigure, operational_figures
from orders.forms import StaffOrderFilterForm


@staff_required
def operational_dashboard(request):
    figures = operational_figures()
    context = {
        "figures": figures,
        "pending_url": _orders_url(figures.pending),
        "overdue_url": _orders_url(figures.overdue),
        # Même libellé que le filtre de la liste, le délai n'est écrit qu'à un endroit.
        "overdue_label": StaffOrderFilterForm.base_fields["overdue"].label,
        # Rouge seulement s'il y a des commandes en retard.
        "overdue_alert": figures.overdue.count > 0,
        "departures_url": _orders_url(figures.departures),
    }
    return render(request, "dashboard/operational.html", context)


def _orders_url(figure: OrderFigure) -> str:
    """Liste des demandes filtrée sur les commandes comptées (booléen vrai : « True », lu comme coché)."""
    return f"{reverse('manage_orders')}?{urlencode(figure.criteria)}"

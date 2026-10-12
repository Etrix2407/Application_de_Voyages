"""Tableau de pilotage : réservé à l'administrateur, mis à jour toutes les heures."""

from django.shortcuts import render

from accounts.decorators import administrator_required
from dashboard.forms import PeriodForm, export_period_form
from dashboard.services.cache import pilotage_snapshot


@administrator_required
def pilotage_dashboard(request):
    form = PeriodForm(request.GET or None)
    period = form.period()
    snapshot = pilotage_snapshot(period)
    context = {
        "form": form,
        "pilotage": snapshot.sections,
        "updated_at": snapshot.computed_at,
        # Lu par le partiel _comparison.html : « par rapport au mois dernier ».
        "compared_to": period.compared_to,
        "export_form": export_period_form(period),
    }
    return render(request, "dashboard/pilotage.html", context)

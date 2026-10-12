"""Export des commandes de la période et journal des exports : réservés à l'administrateur."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.decorators import administrator_required
from dashboard.forms import PeriodForm
from dashboard.models import ExportLog
from dashboard.services.order_export import export_orders as build_export

EXPORTS_PER_PAGE = 25


@administrator_required
@require_POST
@never_cache
def export_orders(request):
    # Données lues à l'instant : le cache du tableau de pilotage n'est pas utilisé.
    form = PeriodForm(request.POST)
    if not form.is_valid():
        messages.error(request, "L'export n'a pas été préparé : la période demandée n'est pas valide.")
        return redirect("pilotage_dashboard")
    export = build_export(form.period(), request.user)
    response = HttpResponse(export.content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{export.file_name}"'
    return response


@administrator_required
def export_log(request):
    page = Paginator(ExportLog.objects.all(), EXPORTS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "dashboard/export_log.html", {"page": page})

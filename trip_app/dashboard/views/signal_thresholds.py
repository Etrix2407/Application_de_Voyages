"""Seuils des signaux du tableau de pilotage : modifiés par l'administrateur, appliqués tout de suite."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required
from dashboard.forms import SignalThresholdsForm
from dashboard.models import SignalThresholds


@administrator_required
def signal_thresholds(request):
    thresholds = SignalThresholds.current()
    form = SignalThresholdsForm(request.POST or None, instance=thresholds)
    if request.method == "POST" and form.is_valid():
        thresholds = form.save(commit=False)
        thresholds.updated_at = timezone.now()
        thresholds.updated_by = request.user
        thresholds.updated_by_name = request.user.get_full_name()
        thresholds.save()
        messages.success(request, "Les seuils des signaux ont été enregistrés. Ils s'appliquent dès maintenant.")
        return redirect("pilotage_dashboard")
    return render(request, "dashboard/signal_thresholds.html", {"form": form, "thresholds": thresholds})

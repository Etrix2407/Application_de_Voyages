"""Pages de gestion des promotions : consultation par le personnel, actions réservées à l'administrateur."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import administrator_required, staff_required
from promotions.forms import PromotionForm
from promotions.models import Promotion, State
from promotions.services.management import (
    PromotionInUse,
    create_promotion,
    delete_promotion,
    disable_promotion,
    update_promotion,
)

PROMOTIONS_PER_PAGE = 25


def _is_used(promotion: Promotion) -> bool:
    """Utilisée par au moins une demande de voyage, même annulée (la demande garde la promotion)."""
    return promotion.orders.exists()


def _promotions():
    return Promotion.objects.prefetch_related("countries", "destinations")


@staff_required
def promotion_list(request):
    page = Paginator(_promotions(), PROMOTIONS_PER_PAGE).get_page(request.GET.get("page"))
    today = timezone.localdate()
    context = {
        "page": page,
        "rows": [(promotion, promotion.state(today)) for promotion in page.object_list],
        "can_manage": request.user.is_administrator,
    }
    return render(request, "promotions/manage/list.html", context)


@staff_required
def promotion_detail(request, pk):
    promotion = get_object_or_404(_promotions(), pk=pk)
    state = promotion.state()
    used = _is_used(promotion)
    context = {
        "promotion": promotion,
        "state": state,
        "history": promotion.history.all(),
        "can_manage": request.user.is_administrator,
        "can_disable": state != State.DISABLED,
        "used": used,
    }
    return render(request, "promotions/manage/detail.html", context)


@administrator_required
def create(request):
    form = PromotionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        promotion = create_promotion(form, request.user)
        messages.success(request, f"La promotion « {promotion} » a été créée.")
        return redirect("manage_promotion_detail", pk=promotion.pk)
    return render(request, "promotions/manage/form.html", {"form": form, "title": "Créer une promotion"})


@administrator_required
def edit(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)
    used = _is_used(promotion)
    form = PromotionForm(request.POST or None, instance=promotion, used=used)
    if request.method == "POST" and form.is_valid():
        update_promotion(form, request.user)
        messages.success(request, f"La promotion « {promotion} » a été enregistrée.")
        return redirect("manage_promotion_detail", pk=promotion.pk)
    context = {"form": form, "title": f"Modifier « {promotion} »", "promotion": promotion, "used": used}
    return render(request, "promotions/manage/form.html", context)


@administrator_required
@require_POST
def disable(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)
    if disable_promotion(promotion, request.user):
        messages.success(request, f"La promotion « {promotion} » est désactivée : elle n'est plus proposée.")
    else:
        messages.error(request, "Cette promotion est déjà désactivée.")
    return redirect("manage_promotion_detail", pk=promotion.pk)


@administrator_required
def delete(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)
    if request.method == "POST":
        try:
            delete_promotion(promotion)
        except PromotionInUse:
            messages.error(
                request,
                f"« {promotion} » a déjà été utilisée dans des demandes de voyage : elle ne peut pas être "
                "supprimée. Vous pouvez la désactiver.",
            )
            return redirect("manage_promotion_detail", pk=promotion.pk)
        messages.success(request, f"La promotion « {promotion} » a été supprimée.")
        return redirect("manage_promotions")
    return render(request, "promotions/manage/delete.html", {"promotion": promotion})

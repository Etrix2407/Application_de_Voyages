"""Pages de gestion des promotions : consultation par le personnel, actions réservées à l'administrateur."""

import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required, staff_required
from accounts.models import User
from orders.services.promotion_statistics import promotion_statistics
from orders.services.promotions import exhausted_promotions
from promotions.forms import PromotionForm, PromotionMailingForm
from promotions.models import Action, Promotion, PromotionState
from promotions.services.management import (
    PromotionInUse,
    PromotionMailed,
    create_promotion,
    delete_promotion,
    disable_promotion,
    update_promotion,
)
from promotions.services.mailing import (
    AlreadySent,
    NoRecipients,
    mailable_promotions,
    mailing_preview,
    send_promotion_mailing,
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
    history = list(promotion.history.all())
    mailings = list(promotion.mailings.all())
    # Auteur de la création, lu dans l'historique déjà chargé (nom figé).
    creation = next((change for change in history if change.action == Action.CREATED), None)
    context = {
        "promotion": promotion,
        "state": state,
        "history": history,
        "created_by": creation.author_name if creation else "",
        "can_manage": request.user.is_administrator,
        "can_disable": state != PromotionState.DISABLED,
        "can_mail": promotion in mailable_promotions(exclude=exhausted_promotions()),
        # Une promotion utilisée ou déjà envoyée par e-mail se désactive, elle ne se supprime pas.
        "can_delete": not used and not mailings,
        "mailings": mailings,
        "used": used,
    }
    return render(request, "promotions/manage/detail.html", context)


@staff_required
def statistics(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)
    context = {"promotion": promotion, "statistics": promotion_statistics(promotion)}
    return render(request, "promotions/manage/statistics.html", context)


@administrator_required
def create(request):
    form = PromotionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        promotion = create_promotion(form, request.user)
        messages.success(request, f"La promotion « {promotion} » a été créée.")
        return redirect("manage_promotion_detail", pk=promotion.pk)
    return render(request, "promotions/manage/form.html", {"form": form, "title": "Créer une promotion"})


@administrator_required
def send_mailing(request):
    """Envoi d'une promotion par e-mail à tous les clients consentants (programmé, pas immédiat).

    Formulaire, puis page de confirmation (nombre de clients, aperçu du texte), puis envoi.
    """
    form = PromotionMailingForm(
        request.POST or None, initial={"promotion": request.GET.get("promotion")}, exclude=exhausted_promotions()
    )
    recipients_count = User.objects.promotion_recipients().count()
    if request.method == "POST" and "edit" not in request.POST and form.is_valid():
        data = form.cleaned_data
        if "confirm" not in request.POST or data["submission_token"] is None:
            return _confirm_mailing(request, form, recipients_count)
        try:
            mailing = send_promotion_mailing(
                data["promotion"], data["message"], request.user, submission_token=data["submission_token"]
            )
        except AlreadySent as duplicate:
            messages.info(request, "Cet envoi avait déjà été programmé : chaque client ne le recevra qu'une fois.")
            return redirect("manage_promotion_detail", pk=duplicate.mailing.promotion_id)
        except NoRecipients:
            messages.error(
                request, "Aucun client n'accepte les e-mails promotionnels pour l'instant : rien n'a été envoyé."
            )
        else:
            count = mailing.recipients_count
            messages.success(
                request,
                f"L'envoi à {count} client{'s' if count > 1 else ''} a été programmé : "
                "les e-mails partent dans les prochaines minutes.",
            )
            return redirect("manage_promotion_detail", pk=mailing.promotion.pk)
    context = {"form": form, "recipients_count": recipients_count}
    return render(request, "promotions/manage/mailing.html", context)


def _confirm_mailing(request, form, recipients_count):
    """Dernière vérification avant l'envoi réel : nombre de clients et aperçu de l'e-mail."""
    data = form.cleaned_data
    subject, body = mailing_preview(data["promotion"], data["message"])
    context = {
        "form": form,
        "promotion": data["promotion"],
        "recipients_count": recipients_count,
        "preview_subject": subject,
        "preview_body": body,
        "submission_token": uuid.uuid4(),
    }
    return render(request, "promotions/manage/mailing_confirm.html", context)


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
def disable(request, pk):
    """Page de confirmation, puis désactivation (définitive) au clic sur le bouton."""
    promotion = get_object_or_404(Promotion, pk=pk)
    if request.method != "POST":
        return render(request, "promotions/manage/disable.html", {"promotion": promotion})
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
        except PromotionMailed:
            messages.error(
                request,
                f"« {promotion} » a déjà été envoyée par e-mail aux clients : elle ne peut pas être "
                "supprimée, pour garder l'historique des envois. Vous pouvez la désactiver.",
            )
            return redirect("manage_promotion_detail", pk=promotion.pk)
        messages.success(request, f"La promotion « {promotion} » a été supprimée.")
        return redirect("manage_promotions")
    return render(request, "promotions/manage/delete.html", {"promotion": promotion})

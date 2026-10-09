"""Gestion du personnel par l'administrateur."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import administrator_required
from accounts.forms import AgentCreationForm, StaffMemberForm
from accounts.models import STAFF_ROLES, User
from accounts.services.staff_rules import check_not_self, send_activation_link


LINK_NOT_SENT = (
    "Le lien n'a pas pu être envoyé (problème de messagerie). "
    "Réessayez plus tard avec « Envoyer un lien de mot de passe »."
)


def _get_staff_member(pk: int) -> User:
    """Seuls les comptes du personnel sont gérés ici, jamais ceux des clients."""
    return get_object_or_404(User, pk=pk, role__in=STAFF_ROLES)


@administrator_required
def staff_list(request):
    members = User.objects.filter(role__in=STAFF_ROLES).order_by("last_name", "first_name", "pk")
    return render(request, "accounts/staff/list.html", {"members": members})


@administrator_required
def create_agent(request):
    form = AgentCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        agent = form.save()
        created = f"Le compte de {agent.get_full_name()} ({agent.employee_number}) a été créé."
        if send_activation_link(request, agent):
            messages.success(request, f"{created} Un e-mail lui a été envoyé pour choisir son mot de passe.")
        else:
            messages.warning(request, f"{created} {LINK_NOT_SENT}")
        return redirect("staff_list")
    return render(request, "accounts/staff/create.html", {"form": form})


@administrator_required
def edit_staff_member(request, pk):
    member = _get_staff_member(pk)
    form = StaffMemberForm(request.POST or None, instance=member, actor=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Le compte de {member.get_full_name()} a été mis à jour.")
        return redirect("staff_list")
    return render(request, "accounts/staff/edit.html", {"form": form, "member": member})


@administrator_required
@require_POST
def set_staff_active(request, pk, active: bool):
    member = _get_staff_member(pk)
    try:
        check_not_self(member, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("staff_list")
    member.is_active = active
    member.save(update_fields=["is_active"])
    state = "réactivé" if active else "désactivé"
    messages.success(request, f"Le compte de {member.get_full_name()} a été {state}.")
    return redirect("staff_list")


@administrator_required
@require_POST
def resend_link(request, pk):
    member = _get_staff_member(pk)
    if not member.is_active:
        messages.error(request, "Ce compte est désactivé : réactivez-le avant d'envoyer un lien.")
    elif send_activation_link(request, member):
        messages.success(request, f"Un nouveau lien a été envoyé à {member.email}.")
    else:
        messages.error(request, LINK_NOT_SENT)
    return redirect("staff_list")


@administrator_required
def delete_staff_member(request, pk):
    member = _get_staff_member(pk)
    try:
        check_not_self(member, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("staff_list")
    if request.method == "POST":
        member.delete()
        messages.success(request, f"Le compte de {member.get_full_name()} a été supprimé.")
        return redirect("staff_list")
    return render(request, "accounts/staff/delete.html", {"member": member})

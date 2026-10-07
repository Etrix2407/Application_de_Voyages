"""Vues des comptes : inscription, connexion, profil, personnel."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .decorators import administrator_required, client_required
from .forms import (
    AgentCreationForm,
    LoginForm,
    SignUpForm,
    StaffMemberForm,
    ClientProfileForm,
    AccountDeletionForm,
)
from .models import STAFF_ROLES, User
from .staff import send_activation_link, check_not_self


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Bienvenue {user.first_name}, votre compte a été créé.")
        return redirect("home")
    return render(request, "accounts/sign_up.html", {"form": form})


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def profile(request):
    return render(request, "accounts/profile.html")


@client_required
def edit_profile(request):
    form = ClientProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vos informations ont été enregistrées.")
        return redirect("profile")
    return render(request, "accounts/edit_profile.html", {"form": form})


class AccountPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("profile")
    success_message = "Votre mot de passe a été modifié."


@client_required
def delete_account(request):
    form = AccountDeletionForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Votre compte et vos données ont été supprimés.")
        return redirect("home")
    return render(request, "accounts/delete_account.html", {"form": form})


def _get_staff_member(pk: int) -> User:
    """Seuls les comptes du personnel sont gérés ici, jamais ceux des clients."""
    return get_object_or_404(User, pk=pk, role__in=STAFF_ROLES)


@administrator_required
def staff_list(request):
    members = User.objects.filter(role__in=STAFF_ROLES).order_by("last_name", "first_name")
    return render(request, "accounts/staff/list.html", {"members": members})


@administrator_required
def create_agent(request):
    form = AgentCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        agent = form.save()
        send_activation_link(request, agent)
        messages.success(
            request,
            f"Le compte de {agent.get_full_name()} ({agent.employee_number}) a été créé. "
            "Un e-mail lui a été envoyé pour choisir son mot de passe.",
        )
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
    send_activation_link(request, member)
    messages.success(request, f"Un nouveau lien a été envoyé à {member.email}.")
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

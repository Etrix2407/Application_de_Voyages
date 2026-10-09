"""Profil de l'utilisateur connecté : consultation, modification, mot de passe, suppression."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from accounts.decorators import client_required
from accounts.forms import AccountDeletionForm, ClientProfileForm


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

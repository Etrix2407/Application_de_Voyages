"""Profil de l'utilisateur connecté : consultation, modification, mot de passe, suppression."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from accounts.decorators import client_required
from accounts.forms import AccountDeletionForm, ClientProfileForm, EmailChangeForm
from accounts.services.email_change import apply_email_change, pending_email_change, request_email_change


@login_required
def profile(request):
    return render(request, "accounts/profile/detail.html")


@client_required
def edit_profile(request):
    form = ClientProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vos informations ont été enregistrées.")
        return redirect("profile")
    return render(request, "accounts/profile/edit.html", {"form": form})


class AccountPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/profile/change_password.html"
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
    return render(request, "accounts/profile/delete.html", {"form": form})


@client_required
def change_email(request):
    form = EmailChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        request_email_change(request, request.user, form.cleaned_data["new_email"])
        # Même message dans tous les cas : rien ne révèle si l'adresse est déjà prise.
        messages.success(
            request,
            "Si cette adresse peut être utilisée, un lien de confirmation vient d'y être envoyé. "
            "Votre adresse ne changera qu'après un clic sur ce lien.",
        )
        return redirect("profile")
    return render(request, "accounts/profile/change_email.html", {"form": form})


def confirm_email_change(request, token):
    """Lien reçu à la nouvelle adresse : la page demande un clic sur un bouton (POST).

    Ouvrir le lien ne change rien : les logiciels qui inspectent les liens des e-mails
    ne peuvent pas appliquer le changement à la place de la personne.
    """
    pending = pending_email_change(token)
    if pending is None:
        return render(request, "accounts/profile/email_change_invalid.html")
    user, new_email = pending
    if request.method != "POST":
        return render(request, "accounts/profile/confirm_email_change.html", {"new_email": new_email})
    apply_email_change(user, new_email)
    messages.success(request, f"Votre adresse e-mail est maintenant {new_email}.")
    return redirect("profile" if request.user.is_authenticated else "login")

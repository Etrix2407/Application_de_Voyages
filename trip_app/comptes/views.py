"""Vues des comptes : inscription, connexion, profil."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .decorators import client_requis
from .forms import ConnexionForm, InscriptionForm, ProfilClientForm, SuppressionCompteForm


def inscription(request):
    if request.user.is_authenticated:
        return redirect("accueil")

    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = form.save()
        login(request, utilisateur)
        messages.success(request, f"Bienvenue {utilisateur.prenom}, votre compte a été créé.")
        return redirect("accueil")
    return render(request, "comptes/inscription.html", {"form": form})


class ConnexionView(LoginView):
    template_name = "comptes/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


@login_required
def profil(request):
    return render(request, "comptes/profil.html")


@client_requis
def modifier_profil(request):
    form = ProfilClientForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vos informations ont été enregistrées.")
        return redirect("profil")
    return render(request, "comptes/modifier_profil.html", {"form": form})


class ChangementMotDePasseView(SuccessMessageMixin, PasswordChangeView):
    template_name = "comptes/changer_mot_de_passe.html"
    success_url = reverse_lazy("profil")
    success_message = "Votre mot de passe a été modifié."


@client_requis
def supprimer_compte(request):
    form = SuppressionCompteForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = request.user
        logout(request)
        utilisateur.delete()
        messages.success(request, "Votre compte et vos données ont été supprimés.")
        return redirect("accueil")
    return render(request, "comptes/supprimer_compte.html", {"form": form})

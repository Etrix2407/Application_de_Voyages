"""Vues d'inscription et de connexion."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import ConnexionForm, InscriptionForm


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

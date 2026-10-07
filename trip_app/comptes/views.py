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

from .decorators import administrateur_requis, client_requis
from .forms import (
    AgentCreationForm,
    ConnexionForm,
    InscriptionForm,
    PersonnelModificationForm,
    ProfilClientForm,
    SuppressionCompteForm,
)
from .models import ROLES_PERSONNEL, Utilisateur
from .personnel import envoyer_lien_activation, verifier_action_sur_soi


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


def _membre_du_personnel(pk: int) -> Utilisateur:
    """Seuls les comptes du personnel sont gérés ici, jamais ceux des clients."""
    return get_object_or_404(Utilisateur, pk=pk, role__in=ROLES_PERSONNEL)


@administrateur_requis
def liste_personnel(request):
    membres = Utilisateur.objects.filter(role__in=ROLES_PERSONNEL).order_by("nom", "prenom")
    return render(request, "comptes/personnel/liste.html", {"membres": membres})


@administrateur_requis
def creer_agent(request):
    form = AgentCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        agent = form.save()
        envoyer_lien_activation(request, agent)
        messages.success(
            request,
            f"Le compte de {agent.get_full_name()} ({agent.numero_employe}) a été créé. "
            "Un e-mail lui a été envoyé pour choisir son mot de passe.",
        )
        return redirect("liste_personnel")
    return render(request, "comptes/personnel/creer.html", {"form": form})


@administrateur_requis
def modifier_membre(request, pk):
    membre = _membre_du_personnel(pk)
    form = PersonnelModificationForm(request.POST or None, instance=membre, acteur=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Le compte de {membre.get_full_name()} a été mis à jour.")
        return redirect("liste_personnel")
    return render(request, "comptes/personnel/modifier.html", {"form": form, "membre": membre})


@administrateur_requis
@require_POST
def changer_activation(request, pk, actif: bool):
    membre = _membre_du_personnel(pk)
    try:
        verifier_action_sur_soi(membre, request.user)
    except ValidationError as erreur:
        messages.error(request, erreur.messages[0])
        return redirect("liste_personnel")
    membre.is_active = actif
    membre.save(update_fields=["is_active"])
    etat = "réactivé" if actif else "désactivé"
    messages.success(request, f"Le compte de {membre.get_full_name()} a été {etat}.")
    return redirect("liste_personnel")


@administrateur_requis
@require_POST
def renvoyer_lien(request, pk):
    membre = _membre_du_personnel(pk)
    envoyer_lien_activation(request, membre)
    messages.success(request, f"Un nouveau lien a été envoyé à {membre.email}.")
    return redirect("liste_personnel")


@administrateur_requis
def supprimer_membre(request, pk):
    membre = _membre_du_personnel(pk)
    try:
        verifier_action_sur_soi(membre, request.user)
    except ValidationError as erreur:
        messages.error(request, erreur.messages[0])
        return redirect("liste_personnel")
    if request.method == "POST":
        membre.delete()
        messages.success(request, f"Le compte de {membre.get_full_name()} a été supprimé.")
        return redirect("liste_personnel")
    return render(request, "comptes/personnel/supprimer.html", {"membre": membre})

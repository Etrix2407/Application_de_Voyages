"""Inscription (avec confirmation de l'adresse e-mail), connexion et liens pour choisir un mot de passe."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from accounts.forms import LoginForm, ResendConfirmationForm, SignUpForm
from accounts.services import sign_up as sign_up_service
from accounts.services.password_links import agent_invitation_token_generator
from accounts.services.password_notice import send_password_changed_notice
from accounts.services.throttling import (
    confirmation_requests_by_ip,
    get_client_ip,
    recent_sign_ups_by_ip,
    sign_ups_by_ip,
    unlock_login,
)


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)
    ip = get_client_ip(request)
    if request.method == "POST" and sign_ups_by_ip.is_locked(ip):
        messages.error(request, "Trop d'inscriptions depuis cette connexion. Réessayez dans une heure.")
    elif request.method == "POST" and form.is_valid():
        sign_ups_by_ip.record(ip)
        recent_sign_ups_by_ip.reset(ip)
        recent_sign_ups_by_ip.record(ip)
        sign_up_service.request_sign_up(form.cleaned_data)
        # Même page que l'adresse soit nouvelle ou déjà inscrite : rien n'est révélé.
        return redirect("sign_up_done")
    return render(request, "accounts/auth/sign_up.html", {"form": form})


def sign_up_done(request):
    return render(request, "accounts/auth/sign_up_done.html")


def confirm_sign_up(request, token):
    """Lien reçu par e-mail : la page affiche les données du compte et demande un clic (POST).

    Ouvrir le lien ne confirme rien : la personne vérifie d'abord que ce compte est bien
    le sien, et les logiciels qui inspectent les liens des e-mails ne confirment pas à sa place.
    """
    user = sign_up_service.user_from_token(token)
    if user is None:
        return render(request, "accounts/auth/confirm_sign_up_invalid.html")
    if not user.is_awaiting_confirmation:
        messages.info(request, "Votre adresse est déjà confirmée.")
        return redirect("home" if request.user.is_authenticated else "login")

    if request.method == "POST":
        sign_up_service.confirm(user)
        messages.success(request, f"Merci {user.first_name}, votre adresse e-mail est confirmée.")
        return redirect("home" if request.user.is_authenticated else "login")
    return render(request, "accounts/auth/confirm_sign_up.html", {"account": user})


def resend_confirmation(request):
    if request.user.is_authenticated:
        return _resend_to_logged_in_user(request)

    form = ResendConfirmationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ip = get_client_ip(request)
        if not confirmation_requests_by_ip.is_locked(ip):
            confirmation_requests_by_ip.record(ip)
            sign_up_service.resend_confirmation(form.cleaned_data["email"])
        # Réponse identique dans tous les cas : rien n'est révélé.
        return redirect("sign_up_done")
    return render(request, "accounts/auth/resend_confirmation.html", {"form": form})


def _resend_to_logged_in_user(request):
    """Client connecté : le lien part à l'adresse de son compte, sans rien saisir."""
    if not request.user.is_awaiting_confirmation:
        messages.info(request, "Votre adresse e-mail est déjà confirmée.")
        return redirect("profile")
    if request.method == "POST":
        if sign_up_service.send_confirmation(request.user):
            messages.success(request, f"Un nouveau lien de confirmation vient d'être envoyé à {request.user.email}.")
        else:
            messages.error(request, "Le lien n'a pas pu être envoyé pour le moment. Réessayez plus tard.")
        return redirect("profile")
    return render(request, "accounts/auth/resend_confirmation.html")


class AccountLoginView(LoginView):
    template_name = "accounts/auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    # LoginView remplace le nom du site par le nom de domaine : on garde celui de l'agence.
    extra_context = {"site_name": settings.SITE_NAME}


class EmailLinkPasswordView(PasswordResetConfirmView):
    """Mot de passe choisi par un lien reçu par e-mail.

    - Un compte désactivé (agent qui a quitté l'agence) ne peut plus se servir d'un lien reçu avant.
    - Une alerte de sécurité est envoyée ensuite, sauf à la toute première définition (agent invité,
      qui n'avait pas encore de mot de passe).
    - La connexion bloquée après trop d'échecs redevient possible depuis l'appareil utilisé.
    """

    success_url = reverse_lazy("password_reset_complete")

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user is not None and user.is_active else None

    def form_valid(self, form):
        had_password = self.user.has_usable_password()
        response = super().form_valid(form)
        unlock_login(self.user.email, get_client_ip(self.request))
        if had_password:
            send_password_changed_notice(self.user)
        return response


class AccountPasswordResetConfirmView(EmailLinkPasswordView):
    """Lien « mot de passe oublié », ou lien envoyé à un client par un agent (valable 1 heure)."""

    template_name = "accounts/auth/password_reset_confirm.html"


class AgentActivationView(EmailLinkPasswordView):
    """Lien d'invitation d'un agent (valable 7 jours), aussi renvoyé depuis la liste du personnel."""

    template_name = "accounts/auth/activate_account.html"
    token_generator = agent_invitation_token_generator

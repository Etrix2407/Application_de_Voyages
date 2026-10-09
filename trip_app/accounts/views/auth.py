"""Inscription (avec confirmation de l'adresse e-mail) et connexion."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from accounts.forms import LoginForm, ResendConfirmationForm, SignUpForm
from accounts.services import sign_up as sign_up_service
from accounts.services.throttling import confirmation_requests_by_ip, get_client_ip, sign_ups_by_ip


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)
    ip = get_client_ip(request)
    if request.method == "POST" and sign_ups_by_ip.is_locked(ip):
        messages.error(request, "Trop d'inscriptions depuis cette connexion. Réessayez dans une heure.")
    elif request.method == "POST" and form.is_valid():
        sign_ups_by_ip.record(ip)
        sign_up_service.request_sign_up(request, form)
        # Même page que l'adresse soit nouvelle ou déjà inscrite : rien n'est révélé.
        return redirect("sign_up_done")
    return render(request, "accounts/auth/sign_up.html", {"form": form})


def sign_up_done(request):
    return render(request, "accounts/auth/sign_up_done.html")


def confirm_sign_up(request, token):
    """Le lien reçu par e-mail : la personne choisit son mot de passe, puis le compte est activé."""
    user = sign_up_service.user_from_token(token)
    if user is None:
        return render(request, "accounts/auth/confirm_sign_up_invalid.html")
    if not user.is_awaiting_confirmation:
        messages.info(request, "Votre adresse est déjà confirmée : vous pouvez vous connecter.")
        return redirect("login")

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        sign_up_service.confirm(user, form.cleaned_data["new_password1"])
        login(request, user)
        messages.success(request, f"Bienvenue {user.first_name}, votre compte est activé.")
        return redirect("home")
    return render(request, "accounts/auth/confirm_sign_up.html", {"form": form, "user": user})


def resend_confirmation(request):
    form = ResendConfirmationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ip = get_client_ip(request)
        if not confirmation_requests_by_ip.is_locked(ip):
            confirmation_requests_by_ip.record(ip)
            sign_up_service.resend_confirmation(request, form.cleaned_data["email"])
        # Réponse identique dans tous les cas : rien n'est révélé.
        return redirect("sign_up_done")
    return render(request, "accounts/auth/resend_confirmation.html", {"form": form})


class AccountLoginView(LoginView):
    template_name = "accounts/auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

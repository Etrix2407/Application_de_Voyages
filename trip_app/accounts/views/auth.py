"""Inscription et connexion."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from accounts.forms import LoginForm, SignUpForm
from accounts.services.throttling import get_client_ip, sign_ups_by_ip


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)
    ip = get_client_ip(request)
    if request.method == "POST" and sign_ups_by_ip.is_locked(ip):
        messages.error(request, "Trop de comptes ont été créés depuis cette connexion. Réessayez dans une heure.")
    elif request.method == "POST" and form.is_valid():
        user = form.save()
        sign_ups_by_ip.record(ip)
        login(request, user)
        messages.success(request, f"Bienvenue {user.first_name}, votre compte a été créé.")
        return redirect("home")
    return render(request, "accounts/auth/sign_up.html", {"form": form})


class AccountLoginView(LoginView):
    template_name = "accounts/auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

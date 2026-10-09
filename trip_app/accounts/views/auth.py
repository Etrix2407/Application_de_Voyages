"""Inscription et connexion."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from accounts.forms import LoginForm, SignUpForm


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Bienvenue {user.first_name}, votre compte a été créé.")
        return redirect("home")
    return render(request, "accounts/auth/sign_up.html", {"form": form})


class AccountLoginView(LoginView):
    template_name = "accounts/auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

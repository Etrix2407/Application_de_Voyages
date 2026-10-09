"""Formulaires des comptes : inscription, connexion, profil, personnel."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.core.exceptions import ValidationError

from .models import STAFF_ROLES, Role, User, normalize_email_address
from .services.throttling import (
    get_client_ip,
    login_failures,
    login_failures_by_ip,
    password_reset_requests,
    password_reset_requests_by_ip,
)
from .services.staff_rules import check_not_self


CLIENT_FIELDS = ("first_name", "last_name", "email", "phone", "birth_date")
CLIENT_WIDGETS = {
    "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    "email": forms.EmailInput(attrs={"autocomplete": "email"}),
    "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
}
CLIENT_HELP_TEXTS = {"phone": "Facultatif. Exemple : 0470 12 34 56, ou +33 6 12 34 56 78 depuis l'étranger."}


class SignUpForm(forms.ModelForm):
    """Inscription sans mot de passe : il sera choisi après confirmation de l'adresse."""

    consent = forms.BooleanField(
        label="J'ai lu et j'accepte la politique de confidentialité.",
        error_messages={"required": "Vous devez accepter la politique de confidentialité."},
    )

    class Meta:
        model = User
        fields = CLIENT_FIELDS
        widgets = CLIENT_WIDGETS
        help_texts = CLIENT_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].required = True
        # Le rôle doit être connu avant la validation du modèle (règles propres aux clients).
        self.instance.role = Role.CLIENT

    def validate_unique(self) -> None:
        # Volontairement vide : dire « adresse déjà utilisée » révélerait qui est client.
        # Le service d'inscription gère ce cas sans le révéler.
        pass


class ResendConfirmationForm(forms.Form):
    email = forms.EmailField(
        label="Adresse e-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Adresse e-mail ou mot de passe incorrect.",
        "locked": (
            "Trop de tentatives échouées. Pour votre sécurité, réessayez dans 15 minutes "
            "ou utilisez « Mot de passe oublié »."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Adresse e-mail"

    def clean(self):
        email = self.cleaned_data.get("username") or ""
        ip = get_client_ip(self.request)
        if (email and login_failures.is_locked(email)) or login_failures_by_ip.is_locked(ip):
            raise ValidationError(self.error_messages["locked"], code="locked")
        try:
            cleaned_data = super().clean()
        except ValidationError:
            if email:
                login_failures.record(email)
            login_failures_by_ip.record(ip)
            raise
        # Le compteur de l'IP n'est pas remis à zéro : un compte valide ne doit pas
        # permettre de relancer une série d'essais sur d'autres comptes.
        login_failures.reset(email)
        return cleaned_data


class PasswordResetRequestForm(PasswordResetForm):
    """« Mot de passe oublié » limité par adresse, pour empêcher d'inonder une boîte e-mail.

    Au-delà de la limite, aucun e-mail ne part mais la page affichée reste la même :
    rien ne révèle si l'adresse existe ni si la limite est atteinte.
    """

    def save(self, *args, request=None, **kwargs) -> None:
        email = self.cleaned_data["email"]
        ip = get_client_ip(request)
        if password_reset_requests.is_locked(email) or password_reset_requests_by_ip.is_locked(ip):
            return
        password_reset_requests.record(email)
        password_reset_requests_by_ip.record(ip)
        super().save(*args, request=request, **kwargs)


class ClientProfileForm(forms.ModelForm):
    """L'e-mail se change à part (mot de passe + lien de confirmation) : voir EmailChangeForm."""

    class Meta:
        model = User
        fields = tuple(field_name for field_name in CLIENT_FIELDS if field_name != "email")
        widgets = CLIENT_WIDGETS
        help_texts = CLIENT_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].required = True


class ClientCorrectionForm(ClientProfileForm):
    """Correction par un agent : ni mot de passe ni e-mail (identifiant géré par le client)."""


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(
        label="Nouvelle adresse e-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label="Votre mot de passe actuel",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user: User, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Mot de passe incorrect.", code="incorrect_password")
        return password

    def clean_new_email(self) -> str:
        new_email = normalize_email_address(self.cleaned_data["new_email"])
        if new_email == self.user.email:
            raise ValidationError("C'est déjà votre adresse actuelle.", code="same_email")
        return new_email


class AccountDeletionForm(forms.Form):
    password = forms.CharField(
        label="Votre mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user: User, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Mot de passe incorrect.", code="incorrect_password")
        return password


class AgentCreationForm(forms.ModelForm):
    """Création d'un agent sans mot de passe : il le choisira via le lien reçu par e-mail."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"email": "Adresse e-mail professionnelle"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le rôle doit être connu avant la validation du modèle (règles propres aux clients).
        self.instance.role = Role.AGENT

    def save(self, commit: bool = True) -> User:
        agent = super().save(commit=False)
        agent.set_unusable_password()
        if commit:
            agent.save()
        return agent


class StaffMemberForm(forms.ModelForm):
    role = forms.ChoiceField(
        label="Rôle", choices=[(role.value, role.label) for role in STAFF_ROLES]
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "role")
        labels = {"email": "Adresse e-mail professionnelle"}

    def __init__(self, *args, actor: User, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)

    def clean_role(self) -> str:
        role = self.cleaned_data["role"]
        if role != self.instance.role:
            check_not_self(self.instance, self.actor)
        return role

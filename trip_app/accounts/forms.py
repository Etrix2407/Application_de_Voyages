"""Formulaires des comptes : inscription, connexion, profil, personnel."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import throttling
from .staff import check_not_self
from .models import STAFF_ROLES, Role, User


CLIENT_FIELDS = ("first_name", "last_name", "email", "phone", "birth_date")
CLIENT_WIDGETS = {
    "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    "email": forms.EmailInput(attrs={"autocomplete": "email"}),
    "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
}
CLIENT_HELP_TEXTS = {"phone": "Facultatif. Exemple : 0470 12 34 56."}


class SignUpForm(BaseUserCreationForm):
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
        self.fields["password1"].label = "Mot de passe"
        self.fields["password2"].label = "Confirmation du mot de passe"

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.role = Role.CLIENT
        user.consent_date = timezone.now()
        if commit:
            user.save()
        return user


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
        if email and throttling.is_locked(email):
            raise ValidationError(self.error_messages["locked"], code="locked")
        try:
            cleaned_data = super().clean()
        except ValidationError:
            if email:
                throttling.record_failure(email)
            raise
        throttling.reset(email)
        return cleaned_data


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = CLIENT_FIELDS
        widgets = CLIENT_WIDGETS
        help_texts = CLIENT_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].required = True


class ClientCorrectionForm(ClientProfileForm):
    """Correction par un agent : ni mot de passe ni e-mail (identifiant géré par le client)."""

    class Meta(ClientProfileForm.Meta):
        fields = tuple(field_name for field_name in CLIENT_FIELDS if field_name != "email")


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

    def save(self, commit: bool = True) -> User:
        member = super().save(commit=False)
        if member.role == Role.AGENT:
            # Un agent rétrogradé perd aussi le statut de superutilisateur.
            member.is_superuser = False
        if commit:
            member.save()
        return member

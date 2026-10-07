"""Formulaires des comptes : inscription, connexion, profil."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import limitation
from .models import Role, Utilisateur


CHAMPS_CLIENT = ("prenom", "nom", "email", "telephone", "date_naissance")
WIDGETS_CLIENT = {
    "date_naissance": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    "email": forms.EmailInput(attrs={"autocomplete": "email"}),
    "telephone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
}
AIDES_CLIENT = {"telephone": "Facultatif. Exemple : 0470 12 34 56."}


class InscriptionForm(BaseUserCreationForm):
    consentement = forms.BooleanField(
        label="J'ai lu et j'accepte la politique de confidentialité.",
        error_messages={"required": "Vous devez accepter la politique de confidentialité."},
    )

    class Meta:
        model = Utilisateur
        fields = CHAMPS_CLIENT
        widgets = WIDGETS_CLIENT
        help_texts = AIDES_CLIENT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_naissance"].required = True
        self.fields["password1"].label = "Mot de passe"
        self.fields["password2"].label = "Confirmation du mot de passe"

    def save(self, commit: bool = True) -> Utilisateur:
        utilisateur = super().save(commit=False)
        utilisateur.role = Role.CLIENT
        utilisateur.date_consentement = timezone.now()
        if commit:
            utilisateur.save()
        return utilisateur


class ConnexionForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Adresse e-mail ou mot de passe incorrect.",
        "bloque": (
            "Trop de tentatives échouées. Pour votre sécurité, réessayez dans 15 minutes "
            "ou utilisez « Mot de passe oublié »."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Adresse e-mail"

    def clean(self):
        email = self.cleaned_data.get("username") or ""
        if email and limitation.est_bloque(email):
            raise ValidationError(self.error_messages["bloque"], code="bloque")
        try:
            cleaned_data = super().clean()
        except ValidationError:
            if email:
                limitation.enregistrer_echec(email)
            raise
        limitation.reinitialiser(email)
        return cleaned_data


class ProfilClientForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = CHAMPS_CLIENT
        widgets = WIDGETS_CLIENT
        help_texts = AIDES_CLIENT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_naissance"].required = True


class SuppressionCompteForm(forms.Form):
    mot_de_passe = forms.CharField(
        label="Votre mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, utilisateur: Utilisateur, *args, **kwargs):
        self.utilisateur = utilisateur
        super().__init__(*args, **kwargs)

    def clean_mot_de_passe(self) -> str:
        mot_de_passe = self.cleaned_data["mot_de_passe"]
        if not self.utilisateur.check_password(mot_de_passe):
            raise ValidationError("Mot de passe incorrect.", code="mot_de_passe_incorrect")
        return mot_de_passe

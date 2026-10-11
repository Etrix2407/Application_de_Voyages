"""Formulaires des comptes : inscription, connexion, profil, personnel."""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordChangeForm,
    PasswordResetForm,
)
from django.core.exceptions import ValidationError

from .models import STAFF_ROLES, EmailKind, EmailText, Role, User, normalize_email_address
from .services.email_texts import DEFAULT_TEXTS, fields_in, has_lone_brace
from .services.password_links import send_password_link
from .services.throttling import (
    get_client_ip,
    login_failures,
    login_failures_after_sign_up_by_ip,
    login_failures_by_account,
    login_failures_by_ip,
    login_key,
    password_confirmations,
    password_reset_requests,
    password_reset_requests_by_ip,
    recent_sign_ups_by_ip,
)
from .services.staff_rules import check_not_self


CLIENT_FIELDS = ("first_name", "last_name", "email", "phone", "birth_date")
# Le site parle d'« e-mail » : même mot dans le message d'erreur de Django.
EMAIL_ERROR_MESSAGES = {"invalid": "Saisissez une adresse e-mail valide."}
# autocomplete : le navigateur peut remplir les informations de la personne (WCAG 1.3.5).
CLIENT_WIDGETS = {
    "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
    "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
    "birth_date": forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}, format="%Y-%m-%d"),
    "email": forms.EmailInput(attrs={"autocomplete": "email"}),
    "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
}
CLIENT_HELP_TEXTS = {"phone": "Facultatif. Exemple : 0470 12 34 56, ou +33 6 12 34 56 78 depuis l'étranger."}
PROMOTIONAL_EMAILS_LABEL = (
    "J'accepte de recevoir par e-mail les offres et promotions d'Horizons Lointains. "
    "Je peux me désinscrire à tout moment."
)


def promotional_emails_field() -> forms.BooleanField:
    """Case facultative, non cochée par défaut (consentement libre, RGPD)."""
    return forms.BooleanField(label=PROMOTIONAL_EMAILS_LABEL, required=False)


class SignUpForm(BaseUserCreationForm):
    """Inscription avec choix du mot de passe (saisi deux fois, vérifié par les validateurs)."""

    consent = forms.BooleanField(
        label="J'ai lu et j'accepte la politique de confidentialité.",
        error_messages={"required": "Vous devez accepter la politique de confidentialité."},
    )
    promotional_emails = promotional_emails_field()

    class Meta:
        model = User
        fields = CLIENT_FIELDS
        widgets = CLIENT_WIDGETS
        help_texts = CLIENT_HELP_TEXTS
        error_messages = {"email": EMAIL_ERROR_MESSAGES}

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
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        error_messages=EMAIL_ERROR_MESSAGES,
    )


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Adresse e-mail ou mot de passe incorrect.",
        # « Mot de passe oublié » débloque le compte depuis l'appareil utilisé (voir unlock_login).
        "locked": (
            "Trop de tentatives échouées. Pour votre sécurité, réessayez dans "
            f"{login_failures.window_text} ou utilisez « Mot de passe oublié »."
        ),
        "locked_ip": (
            "Trop de tentatives échouées depuis cette connexion. "
            f"Réessayez dans {login_failures_by_ip.window_text}."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Adresse e-mail"
        # Champ e-mail : clavier adapté sur téléphone et remplissage automatique.
        self.fields["username"].widget.input_type = "email"
        self.fields["username"].widget.attrs.update(autocomplete="email", inputmode="email")

    def clean(self):
        email = self.cleaned_data.get("username") or ""
        ip = get_client_ip(self.request)
        just_signed_up = recent_sign_ups_by_ip.is_locked(ip)
        account_limits = [(login_failures, login_key(email, ip)), (login_failures_by_account, email)] if email else []
        if login_failures_by_ip.is_locked(ip) or (
            just_signed_up and login_failures_after_sign_up_by_ip.is_locked(ip)
        ):
            raise ValidationError(self.error_messages["locked_ip"], code="locked_ip")
        if any(limiter.is_locked(key) for limiter, key in account_limits):
            raise ValidationError(self.error_messages["locked"], code="locked")
        # L'essai est compté avant la vérification du mot de passe (lente) et non après un échec :
        # des requêtes envoyées en même temps ne dépassent pas la limite du compte.
        # Il est effacé en cas de succès.
        for limiter, key in account_limits:
            limiter.record(key)
        try:
            cleaned_data = super().clean()
        except ValidationError:
            login_failures_by_ip.record(ip)
            if just_signed_up:
                login_failures_after_sign_up_by_ip.record(ip)
            raise
        # Le compteur de l'IP n'est pas remis à zéro : un compte valide ne doit pas
        # permettre de relancer une série d'essais sur d'autres comptes.
        for limiter, key in account_limits:
            limiter.reset(key)
        return cleaned_data


class PasswordResetRequestForm(PasswordResetForm):
    """« Mot de passe oublié » limité par adresse et par IP, pour empêcher d'inonder une boîte e-mail.

    Rien ne révèle si l'adresse existe ni si la limite est atteinte : la page affichée reste la même.
    L'e-mail part tout de suite (après validation de la transaction), sans attendre la tâche
    planifiée : un client qui a oublié son mot de passe ne doit pas patienter.
    """

    email = forms.EmailField(
        label="Adresse e-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        error_messages=EMAIL_ERROR_MESSAGES,
    )

    def save(self, *args, request=None, **kwargs) -> None:
        email = self.cleaned_data["email"]
        ip = get_client_ip(request)
        if password_reset_requests.is_locked(email) or password_reset_requests_by_ip.is_locked(ip):
            return
        password_reset_requests.record(email)
        password_reset_requests_by_ip.record(ip)
        # get_users : comptes actifs avec un mot de passe, à cette adresse (sans tenir compte des majuscules).
        for user in self.get_users(email):
            send_password_link(user, EmailKind.PASSWORD_RESET)


class ClientDataForm(forms.ModelForm):
    """L'e-mail se change à part (mot de passe + lien de confirmation) : voir EmailChangeForm."""

    class Meta:
        model = User
        fields = tuple(field_name for field_name in CLIENT_FIELDS if field_name != "email")
        widgets = CLIENT_WIDGETS
        help_texts = CLIENT_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].required = True


class ClientProfileForm(ClientDataForm):
    """Profil modifié par le client lui-même, avec son choix pour les e-mails promotionnels."""

    promotional_emails = promotional_emails_field()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["promotional_emails"].initial = self.instance.accepts_promotional_emails

    def save(self, commit: bool = True) -> User:
        self.instance.set_promotional_emails_consent(self.cleaned_data["promotional_emails"])
        return super().save(commit)


class ClientCorrectionForm(ClientDataForm):
    """Correction par un agent : ni mot de passe ni e-mail (identifiant géré par le client),
    ni consentement aux e-mails promotionnels (choix du client seul)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Les données sont celles du client : le navigateur ne doit pas proposer celles de l'agent.
        for field in self.fields.values():
            field.widget.attrs["autocomplete"] = "off"


TOO_MANY_PASSWORD_ATTEMPTS = f"Trop d'essais. Pour votre sécurité, réessayez dans {password_confirmations.window_text}."


def check_current_password(user: User, password: str) -> None:
    """Vérifie le mot de passe actuel d'un utilisateur connecté, avec un nombre d'essais limité."""
    key = f"user-{user.pk}"
    if password_confirmations.is_locked(key):
        raise ValidationError(TOO_MANY_PASSWORD_ATTEMPTS, code="locked")
    if not user.check_password(password):
        password_confirmations.record(key)
        raise ValidationError("Mot de passe incorrect.", code="incorrect_password")
    password_confirmations.reset(key)


class CurrentPasswordForm(forms.Form):
    """Formulaire d'un utilisateur connecté qui ressaisit son mot de passe actuel (champ « password »),
    vérifié par check_current_password. L'utilisateur est le premier argument."""

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
        check_current_password(self.user, password)
        return password


class AccountPasswordChangeForm(PasswordChangeForm):
    def clean_old_password(self) -> str:
        password = self.cleaned_data["old_password"]
        check_current_password(self.user, password)
        return password


class EmailChangeForm(CurrentPasswordForm):
    new_email = forms.EmailField(
        label="Nouvelle adresse e-mail",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        error_messages=EMAIL_ERROR_MESSAGES,
    )
    field_order = ["new_email", "password"]

    def clean_new_email(self) -> str:
        new_email = normalize_email_address(self.cleaned_data["new_email"])
        if new_email == self.user.email:
            raise ValidationError("C'est déjà votre adresse actuelle.", code="same_email")
        return new_email


class AccountDeletionForm(CurrentPasswordForm):
    pass


class AgentCreationForm(forms.ModelForm):
    """Création d'un agent sans mot de passe : il le choisira via le lien reçu par e-mail."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"email": "Adresse e-mail professionnelle"}
        error_messages = {"email": EMAIL_ERROR_MESSAGES}

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
        error_messages = {"email": EMAIL_ERROR_MESSAGES}

    def __init__(self, *args, actor: User, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)

    def clean_role(self) -> str:
        role = self.cleaned_data["role"]
        if role != self.instance.role:
            check_not_self(self.instance, self.actor)
        return role


class EmailTextForm(forms.ModelForm):
    """Objet et texte d'un type d'e-mail, modifiés par l'administrateur.

    Tous les champs variables du type doivent rester dans le texte (au moins une fois) ;
    aucun autre champ ni aucune accolade seule n'est accepté. L'objet ne contient pas de champ.
    """

    class Meta:
        model = EmailText
        fields = ("subject", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 18})}
        help_texts = {
            "body": "Les champs variables s'écrivent entre accolades, par exemple {prénom} : "
            "ils sont remplis à l'envoi. La liste des champs de cet e-mail est donnée plus bas.",
        }

    def clean_subject(self) -> str:
        subject = self.cleaned_data["subject"]
        if "{" in subject or "}" in subject:
            raise ValidationError(
                "L'objet ne peut pas contenir de champ variable ni d'accolade.", code="field_in_subject"
            )
        return subject

    def clean_body(self) -> str:
        # Les navigateurs envoient des fins de ligne Windows : on garde celles des e-mails.
        body = self.cleaned_data["body"].replace("\r\n", "\n")
        expected = DEFAULT_TEXTS[self.instance.kind].fields
        used = fields_in(body)
        errors = []
        unknown = [name for name in dict.fromkeys(used) if name not in expected]
        if unknown:
            errors.append(
                ValidationError(
                    f"{_plural(unknown, 'Champ variable inconnu', 'Champs variables inconnus')} : "
                    f"{_braced(unknown)}. Utilisez seulement les champs de la liste, "
                    "écrits exactement comme indiqué.",
                    code="unknown_field",
                )
            )
        if has_lone_brace(body):
            errors.append(
                ValidationError(
                    "Accolade seule : les accolades { et } servent uniquement à écrire les champs variables, "
                    "par exemple {prénom}.",
                    code="lone_brace",
                )
            )
        missing = [name for name in expected if name not in used]
        if missing:
            errors.append(
                ValidationError(
                    f"{_plural(missing, 'Champ variable manquant', 'Champs variables manquants')} : "
                    f"{_braced(missing)}. Chaque champ de la liste doit rester dans "
                    "le texte : vous pouvez le déplacer, mais pas le supprimer.",
                    code="missing_field",
                )
            )
        if errors:
            raise ValidationError(errors)
        return body


def _braced(names: list[str]) -> str:
    return ", ".join(f"{{{name}}}" for name in names)


def _plural(names: list[str], singular: str, plural: str) -> str:
    return plural if len(names) > 1 else singular
